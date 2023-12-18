import asyncio
import traceback
from server.plexserver import Plexserver
from server.embyserver import Embyserver
from task.base import ScanTask as ST
from util.log import log
from apscheduler.triggers.cron import CronTrigger

class ScanTask(ST):
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver, task_info)

    async def _scan(self,section):
        try:
            if isinstance(self.server,Plexserver):
                name = section.title
            elif isinstance(self.server,Embyserver):
                name = section.Name
            log.info(f"{name}：开始扫描媒体库")
            await section.refresh()
        except (asyncio.CancelledError, KeyboardInterrupt):
                pass
        except:
            log.error(f'{name}扫描媒体库失败：{traceback.format_exc()}')
    
    async def run(self,scheduler):
        log.info(f"{self.server.type.capitalize()}({self.server.name})：开始初始化定时刷新媒体库任务...")
        try:
            if isinstance(self.server,Plexserver):
                librarys = await self.server.library()
                library = librarys.sections()
            elif isinstance(self.server,Embyserver):
                library = await self.server.library()
            for lb in self.library:
                for name,crontab in lb.items():
                    exist = False
                    for lb in library:
                        if isinstance(self.server,Plexserver):
                            lb_name = lb.title
                        elif isinstance(self.server,Embyserver):
                            lb_name = lb.Name
                        if lb_name == name:
                            scheduler.add_job(self._scan,args=[lb], trigger=CronTrigger.from_crontab(crontab))
                            exist = True
                    if not exist:
                        log.info(f"{name}：未在{self.server.type.capitalize()}库中找到{name}库，无法启动此名称刷新媒体库任务，请检查配置文件")
            log.info(f"{self.server.type.capitalize()}({self.server.name})：定时刷新媒体库任务已启动")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{self.server.type.capitalize()}({self.server.name})初始化失败：{traceback.format_exc()}')
