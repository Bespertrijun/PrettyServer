import asyncio
import traceback
import server.embyserver as embyserver
import server.jellyfinserver as jellyfin
from task.base import TitleTask as TT
from util.log import log

class TitleTask(TT):
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver, task_info)

    async def _emby_season_title(self,media):
        try:
            if not media.tmdbid:
                log.warning(f"{self.server.type.capitalize()}: {media.Name} 没有tmdbid，无法搜索季标题，跳过")
                return
            for se in await media.seasons():
                title = await media.season_title(media.tmdbid,se.IndexNumber)
                if title:
                    if se.Name == title:
                        log.info(f'{self.server.type.capitalize()}: {media.Name}: 季{se.IndexNumber} 已存在标题{title}')
                        continue
                    await se.fetchitem()
                    se.data["Name"] = title
                    log.info(f'{self.server.type.capitalize()}: {media.Name}: 改变季{se.IndexNumber}标题为 {title}')
                    await se.edit(se.data)
                else:
                    log.info(f'{self.server.type.capitalize()}: {media.Name}: 季{se.IndexNumber}没有找到相关数据')
        except:
            log.critical(f'{self.server.type.capitalize()}修正季标题任务任务失败 {media.Name}：{traceback.format_exc()}')

    async def run(self):
        log.info(f"{self.server.type.capitalize()}({self.server.name})：开始进行修正季标题任务...")
        try:
            tasks = set()
            emby_library = await self.server.library()
            for lb in emby_library:
                if isinstance(lb,(embyserver.MixContent,jellyfin.MixContent)):
                    data = await lb.get_series()
                elif isinstance(lb,(embyserver.SeriesLibrary,jellyfin.SeriesLibrary)):
                    data = await lb.all()
                else:
                    log.warning(f'{lb.Name}：修正季标题只支持剧集和混合内容库，跳过此库')
                    continue
                for media in data:
                    future = asyncio.create_task(self._emby_season_title(media=media))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
                
            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"{self.server.type.capitalize()}({self.server.name})：修正季标题任务任务执行完毕")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{self.server.type.capitalize()}({self.server.name})修正季标题任务任务失败：{traceback.format_exc()}')