"""
PrettyServer Web 版本启动器
集成调度器和 Web API 服务器
"""
import asyncio
import uvicorn
import warnings
import traceback
import aiohttp
import logging
import os
import bcrypt
from datetime import datetime
from pytz_deprecation_shim import PytzUsageWarning
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from api.app import app
from server.server import get_server, create_server_instance, initialize_server_tasks
from server.embyserver import Embyserver
from server.jellyfinserver import Jellyfinserver
from task.synctask import SyncTask
from task.collectionsynctask import CollectionSyncTask
from conf.conf import CONCURRENT_NUM, SYNC_TASK_LIST, COLLECTION_SYNC_TASK_LIST
from util.log import log
from util.config_manager import CM
import util.globalvar as g

async def on_server_added_callback(server_name: str, server_data: dict):
    """服务器添加回调：添加新服务器实例和任务到运行时"""
    if not g.SCHEDULER:
        log.warning("调度器未初始化，无法添加服务器")
        raise Exception("调度器未初始化")

    # 创建服务器实例
    server = await create_server_instance(server_data)

    if not server:
        log.error(f"无法创建服务器实例: {server_name}")
        raise Exception(f"无法创建服务器实例: {server_name}")

    # 使用辅助函数初始化服务器任务和属性
    initialize_server_tasks(server, server_data, g.TMDB_SESSION, g.SEM)

    # 添加到全局服务器列表
    g.SERVERS.append(server)

    # 初始化服务器任务
    await init_server_task(server, g.SCHEDULER)

    log.info(f"已添加服务器 {server_name} 到运行时")

async def on_server_updated_callback(server_name: str, server_data: dict):
    """服务器更新回调：删除旧实例，创建新实例"""
    try:
        if not g.SCHEDULER:
            log.warning("调度器未初始化，无法更新服务器")
            raise Exception("调度器未初始化")

        # 1. 找到并移除旧的服务器实例
        old_server = None
        for server in g.SERVERS:
            if server.name == server_name:
                old_server = server
                break

        if not old_server:
            log.error(f"服务器 {server_name} 不在运行时列表中")
            raise Exception(f"服务器 {server_name} 不在运行时列表中")

        # 2. 先创建新的服务器实例（如果失败，旧服务器保持不变）
        new_server = await create_server_instance(server_data)
        if not new_server:
            log.error(f"无法创建新服务器实例: {server_data.get('name')}")
            raise Exception(f"无法创建新服务器实例: {server_data.get('name')}")

        # 3. 初始化新服务器的任务和属性
        initialize_server_tasks(new_server, server_data, g.TMDB_SESSION, g.SEM)

        # 4. 新服务器创建成功后，再清理旧服务器
        # 移除旧服务器的所有任务
        task_attrs = ['roletask', 'sorttask', 'scantask', 'mergetask', 'titletask']
        old_server_tasks = []
        for attr in task_attrs:
            if hasattr(old_server, attr):
                old_server_tasks.append(getattr(old_server, attr))

        jobs_removed = 0
        for job in g.SCHEDULER.get_jobs():
            if hasattr(job.func, '__self__') and job.func.__self__ in old_server_tasks:
                job.remove()
                jobs_removed += 1

        log.info(f"已移除服务器 {server_name} 的 {jobs_removed} 个旧任务")

        # 5. 从全局列表中移除旧实例
        g.SERVERS.remove(old_server)

        # 6. 关闭旧服务器连接
        await old_server.close()
        log.info(f"已关闭旧服务器 {server_name} 的连接")

        # 7. 添加新服务器到全局列表
        g.SERVERS.append(new_server)

        # 8. 初始化新服务器的任务
        await init_server_task(new_server, g.SCHEDULER)

        log.info(f"服务器 {server_data.get('name')} 已更新并重新初始化")

    except Exception as e:
        log.error(f"更新服务器 {server_name} 失败: {e}")
        raise

async def on_server_deleted_callback(server_name: str):
    """服务器删除回调：从运行时移除服务器实例和相关任务"""
    try:
        # 1. 在 g.SERVERS 中找到要删除的服务器实例
        server_to_remove = None
        for server in g.SERVERS:
            if server.name == server_name:
                server_to_remove = server
                break

        if server_to_remove is None:
            log.warning(f"服务器 {server_name} 不在运行时列表中，可能已被移除")
            return

        # 2. 获取服务器的所有任务对象（使用并集，自动适配不同服务器类型）
        task_attrs = ['roletask', 'sorttask', 'scantask', 'mergetask', 'titletask']
        server_tasks = []
        for attr in task_attrs:
            if hasattr(server_to_remove, attr):
                server_tasks.append(getattr(server_to_remove, attr))

        # 3. 从调度器中移除该服务器的所有任务
        jobs_removed = 0
        if g.SCHEDULER:
            for job in g.SCHEDULER.get_jobs():
                if hasattr(job.func, '__self__') and job.func.__self__ in server_tasks:
                    job.remove()
                    jobs_removed += 1

        # 4. 关闭服务器连接
        await server_to_remove.close()

        # 5. 从 g.SERVERS 列表中移除该服务器
        g.SERVERS.remove(server_to_remove)

        log.info(f"已从运行时移除服务器 {server_name}，清理了 {jobs_removed} 个任务")

    except Exception as e:
        log.error(f"清理服务器 {server_name} 运行时状态失败: {e}")

async def on_synctask_added_callback(task_name: str, task_data: dict):
    """同步任务添加回调：添加新任务到调度器"""
    if not g.SCHEDULER:
        log.warning("调度器未初始化，无法添加任务")
        raise Exception("调度器未初始化")

    # 创建任务实例（task_data 中的 isfirst 保持原值，用于首次同步判断）
    task = SyncTask(task_data, g.SERVERS)
    # 存储到全局变量
    g.SYNC_TASKS[task_name] = task

    if task.is_run:
        # 将耗时操作放到后台执行
        async def _init_task():
            try:
                if task.first:
                    log.info(f'{task.name} 执行首次同步')
                    await task.synctask()

                log.info(f'{task.name} 初始化同步参数')
                await task.cronsync()
                task.status = 'running'
            except Exception as e:
                log.error(f"任务 {task.name} 初始化失败: {e}")
                task.status = 'failed'

        asyncio.create_task(_init_task())
        g.SCHEDULER.add_job(task.cronsync, trigger='interval', minutes=1)
        log.info(f"已添加新任务: {task_name}")
    else:
        task.status = 'stopped'
        log.info(f"任务 {task_name} 已禁用，不添加到调度器")

async def on_synctask_updated_callback(task_name: str, task_data: dict):
    """同步任务更新回调：刷新任务（非阻塞）"""
    try:
        if not g.SCHEDULER:
            log.warning("调度器未初始化，无法刷新任务")
            return

        # 1. 立即移除旧任务（快速操作）
        for job in g.SCHEDULER.get_jobs():
            if (hasattr(job.func, '__self__') and
                isinstance(job.func.__self__, SyncTask) and
                job.func.__self__.name == task_name):
                job.remove()
                log.info(f"已移除旧任务: {task_name}")
                break

        # 2. 将耗时的任务初始化放到后台执行
        async def _add_task_background():
            try:
                task = SyncTask(task_data, g.SERVERS)
                # 存储到全局变量
                g.SYNC_TASKS[task_name] = task

                if task.is_run:
                    try:
                        if task.first:
                            log.info(f'{task.name} 执行首次同步')
                            await task.synctask()

                        log.info(f'{task.name} 初始化同步参数')
                        await task.cronsync()
                        task.status = 'running'
                    except Exception as e:
                        log.error(f"任务 {task.name} 初始化失败: {e}")
                        task.status = 'failed'

                    g.SCHEDULER.add_job(task.cronsync, trigger='interval', minutes=1)
                    log.info(f"已重新添加任务: {task_name}")
                else:
                    task.status = 'stopped'
                    log.info(f"任务 {task_name} 已禁用，不重新添加到调度器")
            except Exception as e:
                log.error(f"重新添加同步任务 {task_name} 失败: {e}")
                if task_name in g.SYNC_TASKS:
                    g.SYNC_TASKS[task_name].status = 'failed'

        # 创建后台任务，立即返回
        asyncio.create_task(_add_task_background())

    except Exception as e:
        log.error(f"刷新同步任务 {task_name} 失败: {e}")

async def on_synctask_deleted_callback(task_name: str):
    """同步任务删除回调：从调度器移除任务"""
    try:
        if not g.SCHEDULER:
            log.warning("调度器未初始化，无法移除任务")
            return

        # 移除任务
        for job in g.SCHEDULER.get_jobs():
            if (hasattr(job.func, '__self__') and
                isinstance(job.func.__self__, SyncTask) and
                job.func.__self__.name == task_name):
                job.remove()
                log.info(f"已从调度器移除任务: {task_name}")
                break

        # 从全局变量中移除
        if task_name in g.SYNC_TASKS:
            del g.SYNC_TASKS[task_name]
            log.info(f"已从全局变量移除任务: {task_name}")

    except Exception as e:
        log.error(f"移除同步任务 {task_name} 失败: {e}")

async def on_env_updated_callback(env_data: dict):
    """环境配置更新回调：更新运行时环境变量"""
    try:
        # 更新并发数
        if 'concurrent_num' in env_data:
            new_concurrent_num = env_data['concurrent_num']
            if new_concurrent_num != g.SEM._value:
                g.SEM = asyncio.Semaphore(new_concurrent_num)
                log.info(f"已更新并发数: {new_concurrent_num}")

        # 更新代理配置
        if 'proxy' in env_data:
            from conf.conf import PROXY,ISPROXY
            PROXY = env_data['proxy'].get('http', PROXY)
            ISPROXY = env_data['proxy'].get('isproxy', ISPROXY)

        # 更新 TMDB API
        if 'tmdb_api' in env_data:
            from conf.conf import TMDB_API
            TMDB_API = env_data['tmdb_api']
        log.info("环境配置已更新")

    except Exception as e:
        log.error(f"更新环境配置失败: {e}")

async def init_server_task(server, scheduler: AsyncIOScheduler):
    """为单个服务器初始化任务（从 main.py 移植）"""
    if isinstance(server, Jellyfinserver):
        pass
    else:
        if server.roletask.is_run:
            scheduler.add_job(server.roletask.run, trigger=CronTrigger.from_crontab(server.roletask.crontab))
    if server.sorttask.is_run:
        scheduler.add_job(server.sorttask.run, trigger=CronTrigger.from_crontab(server.sorttask.crontab))
    if server.scantask.is_run:
        await server.scantask.run(scheduler)
    if isinstance(server, (Embyserver, Jellyfinserver)):
        if server.mergetask.is_run:
            scheduler.add_job(server.mergetask.run, trigger=CronTrigger.from_crontab(server.mergetask.crontab))
        if server.titletask.is_run:
            scheduler.add_job(server.titletask.run, trigger=CronTrigger.from_crontab(server.titletask.crontab))

async def initialize_passwords():
    """初始化用户密码：将明文密码转换为 bcrypt 哈希"""
    try:
        env_config = CM.get_env()
        users = env_config.get('users', [])
        updated = False

        for user in users:
            password = user.get('password', '')
            # 检查密码是否已经是 bcrypt 哈希（bcrypt 哈希以 $2b$ 或 $2a$ 开头）
            if password and not password.startswith('$2'):
                # 明文密码，需要加密
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                user['password'] = hashed_password.decode('utf-8')
                updated = True
                log.info(f"已将用户 {user.get('username')} 的密码转换为 bcrypt 哈希")

        if updated:
            # 保存更新后的配置
            await CM.update_env(env_config)
            log.info("密码初始化完成，配置已保存")
        else:
            log.info("所有用户密码已经是加密格式")

    except Exception as e:
        log.error(f"初始化密码失败: {e}")
        raise

async def initialize_scheduler():
    """初始化调度器和任务（从 main.py 移植）"""
    try:
        warnings.filterwarnings('ignore', category=PytzUsageWarning)

        # 初始化用户密码
        await initialize_passwords()

        # 初始化调度器
        g.SCHEDULER = AsyncIOScheduler()
        log.info('初始化中.....')

        # 初始化会话和信号量
        g.TMDB_SESSION = aiohttp.ClientSession()
        g.SEM = asyncio.Semaphore(CONCURRENT_NUM)

        # 初始化服务器
        g.SERVERS = await get_server(g.TMDB_SESSION, g.SEM)

        # 为每个服务器添加任务
        for server in g.SERVERS:
            if server.status != 'running':
                log.warning(f"服务器 {server.name} 状态异常: {server.error_msg}，跳过任务初始化")
                continue
            await init_server_task(server, g.SCHEDULER)

        # 添加同步任务
        for task in SYNC_TASK_LIST:
            t = SyncTask(task, g.SERVERS)
            # 存储到全局变量
            g.SYNC_TASKS[t.name] = t

            if t.is_run:
                try:
                    if t.first:
                        await t.synctask()
                    log.info(f'{t.name} 初始化同步参数')
                    await t.cronsync()
                    t.status = 'running'
                    g.SCHEDULER.add_job(t.cronsync, trigger='interval', minutes=1)
                except Exception as e:
                    log.error(f"初始化同步任务 {t.name} 失败: {e}")
                    t.status = 'failed'
            else:
                t.status = 'stopped'

        # 添加合集同步任务
        for task in COLLECTION_SYNC_TASK_LIST:
            t = CollectionSyncTask(task, g.SERVERS)
            if t.is_run:
                log.info(f'{t.name} 初始化合集同步任务')
                g.SCHEDULER.add_job(t.run, trigger=CronTrigger.from_crontab(t.crontab))

        # 启动调度器
        g.SCHEDULER.start()
        log.info(f'启动完成，开始调度任务。共加载 {len(g.SERVERS)} 个服务器，{len(g.SCHEDULER.get_jobs())} 个任务')

        # 注册配置变更回调（用于热重载）
        CM.register_callbacks(
            on_server_added=on_server_added_callback,
            on_server_updated=on_server_updated_callback,
            on_server_deleted=on_server_deleted_callback,
            on_synctask_added=on_synctask_added_callback,
            on_synctask_updated=on_synctask_updated_callback,
            on_synctask_deleted=on_synctask_deleted_callback,
            on_env_updated=on_env_updated_callback
        )
        log.info('已注册配置热重载回调')

    except Exception as e:
        log.critical(f'初始化失败：{traceback.format_exc()}')
        raise

async def cleanup():
    """清理资源"""
    try:
        log.info("退出任务中...")
        if g.SCHEDULER:
            g.SCHEDULER.remove_all_jobs()
        for server in g.SERVERS:
            await server.close()
        if g.TMDB_SESSION:
            await g.TMDB_SESSION.close()
        tasks = asyncio.all_tasks(loop=asyncio.get_running_loop())
        for t in tasks:
            t.cancel()
    except Exception as e:
        log.error(f"清理资源失败: {e}")

async def main():
    """主函数：启动调度器和 Web 服务器"""
    try:
        print("启动 PrettyServer Web 版本...")
        print("Web 界面将在 http://localhost:8000 可用")

        # 配置 Uvicorn 日志输出到文件
        from conf.conf import LOG_PATH
        os.makedirs(LOG_PATH, exist_ok=True)
        uvicorn_log_file = os.path.join(LOG_PATH, f'uvicorn_{datetime.now().strftime("%Y-%m-%d")}.log')

        # 配置 uvicorn 日志处理器
        file_handler = logging.FileHandler(uvicorn_log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        # 为 uvicorn 的各个 logger 添加文件处理器
        for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
            logger = logging.getLogger(logger_name)
            logger.addHandler(file_handler)

        # 初始化调度器和任务
        await initialize_scheduler()

        # 启动 Web 服务器
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    except KeyboardInterrupt:
        print("\n正在关闭 PrettyServer...")
        await cleanup()
    except Exception as e:
        log.critical(f"启动失败: {traceback.format_exc()}")
        await cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已关闭")
    except Exception as e:
        print(f"启动失败: {e}")