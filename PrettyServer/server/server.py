import traceback
from server.plexserver import Plexserver
from server.embyserver import Embyserver
from util.log import log
from conf.conf import check_exist,SERVER_LIST
from task.roletask import PlexRoleTask,EmbyRoleTask
from task.sorttask import SortTask
from task.scantask import ScanTask
from task.mergetask import MergeTask
from task.titletask import TitleTask

async def get_server(tmdb_session,sem):
    servers = []
    try:
        for server in SERVER_LIST:
            if server.get("type").lower() == "plex":
                s = Plexserver(check_exist(server,"url","plex") ,check_exist(server,"token","plex"))
                await s.library()
            elif server.get("type").lower() == "emby":
                s = Embyserver(check_exist(server,"url","emby"),check_exist(server,"token","emby"),
                                check_exist(server,"username","emby"),check_exist(server,"password","emby"))
                if server.get("token") == None:
                    await s.login()
            s.tmdb_session = tmdb_session
            s.sem = sem
            s.name = check_exist(server,"name",'server')
            if isinstance(s,Plexserver):
                s.roletask = PlexRoleTask(s,check_exist(server,"roletask",s.name))
            elif isinstance(s,Embyserver):
                s.roletask = EmbyRoleTask(s,check_exist(server,"roletask",s.name))
            s.sorttask = SortTask(s,check_exist(server,"sorttask",s.name))
            s.scantask = ScanTask(s,check_exist(server,"scantask",s.name))
            if isinstance(s,Embyserver):
                s.mergetask = MergeTask(s,check_exist(server,"mergetask",s.name))
                s.titletask = TitleTask(s,check_exist(server,"titletask",s.name))
            servers.append(s)
        return servers
    except:
        log.critical(f'初始化服务器失败：{traceback.format_exc()}')