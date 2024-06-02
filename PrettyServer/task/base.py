from asyncio import Lock
from conf.conf import check_exist
from server.plexserver import Plexserver
from server.embyserver import Embyserver
from server.jellyfinserver import Jellyfinserver
class BaseTask():
    def __init__(self, mediaserver, task_info:dict) -> None:
        self.server = mediaserver
        self._info = task_info
        self.is_run = check_exist(self._info, "run", list(self._info.keys())[0])

class SyncTask():
    """
        同步任务基本类
    """
    def __init__(self, task_info: dict, servers) -> None:
        self._info = task_info
        self.name = check_exist(self._info, "name", 'Synctask')
        self.is_run = check_exist(self._info, "run", 'Synctask')
        self._loadinfo()
        self.lock = Lock()
        self.plex = self.emby = self.jellyfin = self.plex2 = None
        for server in servers:
            if server.name in self.which:
                if isinstance(server,Plexserver) and self.plex == None:
                    self.plex = server
                elif (self.emby == None and self.jellyfin == None) and isinstance(server,(Jellyfinserver,Embyserver)):
                    self.emby = server
                elif isinstance(server,(Jellyfinserver,Embyserver)):
                    self.jellyfin = server
                elif isinstance(server,Plexserver):
                    self.plex2 = server

    def _loadinfo(self):
        self.first = check_exist(self._info, "isfirst", self.name)
        self.which = check_exist(self._info, "which", self.name)

class MergeTask(BaseTask):
    """
        合并任务基本类
    """
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver,task_info)
        self._loadinfo()

    def _loadinfo(self):
        self.crontab = check_exist(self._info, "crontab", list(self._info.keys())[0])
    
class RoleTask(BaseTask):
    """
        中文化演员基本类
    """
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver,task_info)
        self._loadinfo()

    def _loadinfo(self):
        self.crontab = check_exist(self._info, "crontab", list(self._info.keys())[0])

class SortTask(BaseTask):
    """
        标题任务基本类
    """
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver,task_info)
        self._loadinfo()

    def _loadinfo(self):
        self.crontab = check_exist(self._info, "crontab", list(self._info.keys())[0])

class TitleTask(BaseTask):
    """
        季标题任务基本类
    """
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver,task_info)
        self._loadinfo()

    def _loadinfo(self):
        self.crontab = check_exist(self._info, "crontab", list(self._info.keys())[0])

class ScanTask(BaseTask):
    """
        扫库任务基本类
    """
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver,task_info)
        self._loadinfo()

    def _loadinfo(self):
        self.library = check_exist(self._info, "library", list(self._info.keys())[0])