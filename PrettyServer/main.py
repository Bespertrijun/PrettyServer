import asyncio
import traceback
import warnings
import aiohttp
from pytz_deprecation_shim import PytzUsageWarning
from server.server import get_server
from server.embyserver import Embyserver
from task.synctask import SyncTask
from util.log import log
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from conf.conf import CONCURRENT_NUM,SYNC_TASK_LIST

async def init_server_task(server,scheduler:AsyncIOScheduler):
    if server.roletask.is_run:
        scheduler.add_job(server.roletask.run,trigger=CronTrigger.from_crontab(server.roletask.crontab))
    if server.sorttask.is_run:
        scheduler.add_job(server.sorttask.run,trigger=CronTrigger.from_crontab(server.sorttask.crontab))
    if server.scantask.is_run:
        await server.scantask.run(scheduler)
    if isinstance(server,Embyserver):
        if server.mergetask.is_run:
            scheduler.add_job(server.mergetask.run,trigger=CronTrigger.from_crontab(server.mergetask.crontab))
        if server.titletask.is_run:
            scheduler.add_job(server.titletask.run,trigger=CronTrigger.from_crontab(server.titletask.crontab))

async def main():
    try:
        warnings.filterwarnings('ignore', category=PytzUsageWarning)
        scheduler = AsyncIOScheduler()
        log.info('初始化中.....')
        tmdb_session = aiohttp.ClientSession()
        sem = asyncio.Semaphore(CONCURRENT_NUM)
        servers = await get_server(tmdb_session,sem)
        for server in servers:
            await init_server_task(server,scheduler)
        for task in SYNC_TASK_LIST:
            t = SyncTask(task,servers)
            if t.is_run:
                if t.first:
                    await t.synctask()
                log.info(f'{t.name} 初始化同步参数')
                await t.cronsync()
                scheduler.add_job(t.cronsync, trigger='interval',minutes=1)
        scheduler.start()
        log.info('启动完成，开始调度任务')
        while True:
            await asyncio.sleep(6000)
    except:
        log.critical(traceback.format_exc())
        log.info("退出任务中...")
        scheduler.remove_all_jobs()
        for server in servers:
            await server.close()
        await tmdb_session.close()
        tasks = asyncio.all_tasks(loop=asyncio.get_running_loop())
        for t in tasks:
            t.cancel()
        import sys
        if sys.version_info.minor >= 10:
            await asyncio.wait(tasks)
        else:
            await asyncio.wait(tasks,loop=asyncio.get_running_loop())

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except:
        pass