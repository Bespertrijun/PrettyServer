import asyncio
import traceback
from server.plexserver import Plexserver
from server.embyserver import Embyserver
from server.jellyfinserver import Jellyfinserver
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
            elif isinstance(self.server,(Embyserver,Jellyfinserver)):
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
            elif isinstance(self.server,(Embyserver,Jellyfinserver)):
                library = await self.server.library()
            # 新格式：library = {"库id": {"name": "库名", "crontab": "表达式"}, ...}
            for lib_id, lib_config in self.library.items():
                name = lib_config.get('name')
                crontab = lib_config.get('crontab')

                if not name or not crontab:
                    log.warning(f"库配置不完整，跳过：{lib_config}")
                    continue

                exist = False
                for lb in library:
                    if isinstance(self.server, Plexserver):
                        lb_id = str(lb.key)
                    elif isinstance(self.server, (Embyserver, Jellyfinserver)):
                        lb_id = lb.Id

                    if lb_id == lib_id:
                        scheduler.add_job(self._scan, args=[lb], trigger=CronTrigger.from_crontab(crontab))
                        exist = True
                        break
                if not exist:
                    log.info(f"{name}(ID:{lib_id})：未在{self.server.type.capitalize()}库中找到此库，无法启动刷新媒体库任务，请检查配置文件")
            log.info(f"{self.server.type.capitalize()}({self.server.name})：定时刷新媒体库任务已启动")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{self.server.type.capitalize()}({self.server.name})初始化失败：{traceback.format_exc()}')
