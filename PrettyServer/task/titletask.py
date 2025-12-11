import asyncio
import traceback
import server.embyserver as embyserver
import server.jellyfinserver as jellyfin
from task.base import TitleTask as TT
from util.log import log

class TitleTask(TT):
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver, task_info)

    async def _emby_season_title(self, media):
        """修改剧集的季标题"""
        async with self.server.sem:
            try:
                if not media.tmdbid:
                    log.warning(f"{self.server.type.capitalize()}: {media.Name} 没有tmdbid，无法搜索季标题，跳过")
                    return
                for se in await media.seasons():
                    title = await media.season_title(media.tmdbid, se.IndexNumber)
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
                log.critical(f'{self.server.type.capitalize()}修正季标题任务失败 {media.Name}：{traceback.format_exc()}')

    async def _emby_show_title(self, media):
        """修改剧集标题"""
        async with self.server.sem:
            try:
                if not media.tmdbid:
                    log.warning(f"{self.server.type.capitalize()}: {media.Name} 没有tmdbid，无法搜索剧集标题，跳过")
                    return
                title = await media.show_title(media.tmdbid)
                if title:
                    if media.Name == title:
                        log.info(f'{self.server.type.capitalize()}: {media.Name} 已存在中文标题')
                        return
                    await media.fetchitem()
                    media.data["Name"] = title
                    log.info(f'{self.server.type.capitalize()}: {media.Name} 改变标题为 {title}')
                    await media.edit(media.data)
                else:
                    log.info(f'{self.server.type.capitalize()}: {media.Name} 没有找到中文标题')
            except:
                log.critical(f'{self.server.type.capitalize()}修正剧集标题任务失败 {media.Name}：{traceback.format_exc()}')

    async def _emby_movie_title(self, media):
        """修改电影标题"""
        async with self.server.sem:
            try:
                if not media.tmdbid:
                    log.warning(f"{self.server.type.capitalize()}: {media.Name} 没有tmdbid，无法搜索电影标题，跳过")
                    return
                title = await media.movie_title(media.tmdbid)
                if title:
                    if media.Name == title:
                        log.info(f'{self.server.type.capitalize()}: {media.Name} 已存在中文标题')
                        return
                    await media.fetchitem()
                    media.data["Name"] = title
                    log.info(f'{self.server.type.capitalize()}: {media.Name} 改变标题为 {title}')
                    await media.edit(media.data)
                else:
                    log.info(f'{self.server.type.capitalize()}: {media.Name} 没有找到中文标题')
            except:
                log.critical(f'{self.server.type.capitalize()}修正电影标题任务失败 {media.Name}：{traceback.format_exc()}')

    async def run(self):
        log.info(f"{self.server.type.capitalize()}({self.server.name})：开始进行标题修正任务...")
        try:
            tasks = set()
            emby_library = await self.server.library()

            for lb in emby_library:
                # 处理电影标题
                if self.movie_title:
                    if isinstance(lb, (embyserver.MixContent, jellyfin.MixContent)):
                        movies = await lb.get_movie()
                        for media in movies:
                            future = asyncio.create_task(self._emby_movie_title(media=media))
                            future.add_done_callback(tasks.discard)
                            tasks.add(future)
                    elif isinstance(lb, (embyserver.MovieLibrary, jellyfin.MovieLibrary)):
                        movies = await lb.all()
                        for media in movies:
                            future = asyncio.create_task(self._emby_movie_title(media=media))
                            future.add_done_callback(tasks.discard)
                            tasks.add(future)

                # 处理剧集标题和季标题
                if self.show_title or self.season_title:
                    if isinstance(lb, (embyserver.MixContent, jellyfin.MixContent)):
                        shows = await lb.get_series()
                    elif isinstance(lb, (embyserver.SeriesLibrary, jellyfin.SeriesLibrary)):
                        shows = await lb.all()
                    else:
                        continue

                    for media in shows:
                        if self.show_title:
                            future = asyncio.create_task(self._emby_show_title(media=media))
                            future.add_done_callback(tasks.discard)
                            tasks.add(future)
                        if self.season_title:
                            future = asyncio.create_task(self._emby_season_title(media=media))
                            future.add_done_callback(tasks.discard)
                            tasks.add(future)

            await asyncio.gather(*tasks, return_exceptions=True)
            log.info(f"{self.server.type.capitalize()}({self.server.name})：标题修正任务执行完毕")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{self.server.type.capitalize()}({self.server.name})标题修正任务失败：{traceback.format_exc()}')
