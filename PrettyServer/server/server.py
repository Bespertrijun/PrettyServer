import traceback
from server.plexserver import Plexserver
from server.embyserver import Embyserver
from server.jellyfinserver import Jellyfinserver
from util.log import log
from util.crypto import crypto_manager
from conf.conf import check_exist,SERVER_LIST
from task.roletask import PlexRoleTask,EmbyRoleTask
from task.sorttask import SortTask
from task.scantask import ScanTask
from task.mergetask import MergeTask
from task.titletask import TitleTask

async def create_server_instance(server_data: dict):
    """
    根据配置创建服务器实例

    Args:
        server_data: 服务器配置数据

    Returns:
        服务器实例 (Plexserver/Embyserver/Jellyfinserver) 或 None
    """
    server_type = server_data.get("type", "").lower()
    server = None

    # 解密密码（如果存在）
    password = server_data.get("password")
    if password:
        password = crypto_manager.decrypt_password(password)

    try:
        if server_type == "plex":
            server = Plexserver(server_data.get("url"), server_data.get("token"))
            await server.library()
        elif server_type == "emby":
            server = Embyserver(
                server_data.get("url"),
                server_data.get("token"),
                server_data.get("username"),
                password
            )
            if server_data.get("username") and password:
                await server.login()
        elif server_type == "jellyfin":
            server = Jellyfinserver(
                server_data.get("url"),
                server_data.get("token"),
                server_data.get("username"),
                password
            )
            if server_data.get("username") and password:
                await server.login()

        # 成功则标记为运行中
        if server:
            server.status = 'running'
            server.name = server_data.get("name")
    except Exception as e:
        log.error(f"创建服务器实例失败: {e}")
        # 失败也标记状态
        if server:
            server.status = 'failed'
            server.error_msg = str(e)
            server.name = server_data.get("name")

    return server

def initialize_server_tasks(server, server_data: dict, tmdb_session, sem):
    """
    为服务器实例初始化任务和属性

    Args:
        server: 服务器实例 (Plexserver/Embyserver/Jellyfinserver)
        server_data: 服务器配置数据
        tmdb_session: TMDB 会话
        sem: 信号量
    """
    server.tmdb_session = tmdb_session
    server.sem = sem
    server.name = server_data.get("name")

    # 设置任务
    if isinstance(server, Plexserver):
        server.roletask = PlexRoleTask(server, server_data.get("roletask", {}))
    elif isinstance(server, Embyserver):
        server.roletask = EmbyRoleTask(server, server_data.get("roletask", {}))

    server.sorttask = SortTask(server, server_data.get("sorttask", {}))
    server.scantask = ScanTask(server, server_data.get("scantask", {}))

    if isinstance(server, (Embyserver, Jellyfinserver)):
        server.mergetask = MergeTask(server, server_data.get("mergetask", {}))
        server.titletask = TitleTask(server, server_data.get("titletask", {}))

async def get_server(tmdb_session,sem):
    servers = []
    try:
        for server in SERVER_LIST:
            # 准备服务器配置数据 (使用 check_exist 确保必要字段存在)
            server_data = {
                "type": server.get("type"),
                "url": check_exist(server, "url", server.get("type", "server")),
                "token": check_exist(server, "token", server.get("type", "server")),
                "username": server.get("username"),
                "password": server.get("password"),
                "name": check_exist(server, "name", 'server'),
                "roletask": server.get("roletask", {}),
                "sorttask": server.get("sorttask", {}),
                "scantask": server.get("scantask", {}),
                "mergetask": server.get("mergetask", {}),
                "titletask": server.get("titletask", {})
            }

            # 创建服务器实例
            s = await create_server_instance(server_data)

            # 无论成功还是失败，都初始化并添加到列表
            if s.status == 'running':
                initialize_server_tasks(s, server_data, tmdb_session, sem)

            servers.append(s)
        return servers
    except:
        log.critical(f'初始化服务器失败：{traceback.format_exc()}')