import traceback
import asyncio
import server.embyserver as embyserver
from server.plexserver import Movie,Episode
from server.plexserver import Show
from task.base import SyncTask as ST
from util.log import log

class SyncTask(ST):
    def __init__(self, task_info: dict, servers) -> None:
        super().__init__(task_info, servers)

    async def _synctask(self,media):
        async with self.plex.sem:
            try:
                await media.fetchitem()
                if not media.guid:
                    log.warning(media.title+': 未找到该条目任何刮削ID，请检查刮削')
                    return
                else:
                    emby_medias = await self.emby.guidsearch(tmdb=media.tmdbid,imdb=media.imdbid,tvdb=media.tvdbid)
                    if not emby_medias:
                        log.info(f'Emby服务器未找到：{media.title}')
                        return
                for emby_media in emby_medias:
                    #电影同步
                    if isinstance(media,Movie) and isinstance(emby_media,embyserver.Movie):
                        #判断plex中该影视是否看过
                        if media.viewOffset or media.viewCount:
                            #同步操作
                            if media.viewCount and emby_media.Played:
                                pass
                            elif media.viewCount and not emby_media.Played:
                                await emby_media.watched()
                                log.info(f'Emby服务器已观看：{media.title}')
                            elif media.viewOffset or emby_media.PlaybackPositionTicks != 0:
                                if int(media.viewOffset)*10000 - \
                                emby_media.PlaybackPositionTicks > 0:
                                    await emby_media.timeline(
                                        media.convertTime(media.viewOffset))
                                    log.info(f'Emby服务器已同步进度：{media.title}')
                                elif int(media.viewOffset)*10000 - \
                                    emby_media.PlaybackPositionTicks < 0:
                                    await media.timeline(emby_media.convertTime(
                                        emby_media.PlaybackPositionTicks))
                                    log.info(f'Plex服务器已同步进度：{media.title}')
                            elif not media.viewCount and emby_media.Played:
                                await media.watched()
                                log.info(f'Plex服务器已观看：{media.title}')
                            else:
                                log.warning(f'someting wrong:{media.title}')
                        else:
                            #若判断plex未看过，接下来判断emby是否看过
                            if emby_media.PlaybackPositionTicks != 0:
                                await media.timeline(emby_media.convertTime(
                                    emby_media.PlaybackPositionTicks))
                                log.info(f'Plex服务器已同步进度：{media.title}')
                            elif emby_media.Played:
                                await media.watched()
                                log.info(f'Plex服务器已观看：{media.title}')
                    #剧集同步
                    elif isinstance(media,Show) and isinstance(emby_media,embyserver.Show):
                        #获取剧集集数
                        emby_eps = await emby_media.episodes()
                        #判断剧集内的集数，emby或者plex是否有观看集数
                        if media.viewCount or emby_media.check_played():
                            plex_eps = await media.episodes()
                            for plex_ep in plex_eps:
                                exist = False
                                #遍历匹配对应集数
                                for emby_ep in emby_eps:
                                    if plex_ep.parentIndex == emby_ep.ParentIndexNumber \
                                        and plex_ep.index == emby_ep.IndexNumber:
                                        exist = True
                                        #集数匹配成功，情况1：都观看了
                                        if plex_ep.viewCount and emby_ep.Played:
                                            pass
                                        #情况2：plex观看而emby未观看
                                        elif plex_ep.viewCount and not emby_ep.Played:
                                            await emby_ep.watched()
                                            log.info(
                                            f'{media.title}.{plex_ep.pretty_ep_out()}：Emby已观看')
                                        #情况3：plex或者emby其中有一个未看完
                                        elif plex_ep.viewOffset or emby_ep.PlaybackPositionTicks != 0:
                                            #判断是否是plex未看完
                                            if plex_ep.viewOffset is None:
                                                plex_ep.viewOffset = 0
                                            #通过减法，判断plex和emby进度条长短
                                            if int(plex_ep.viewOffset)*10000 - \
                                                emby_ep.PlaybackPositionTicks > 0:
                                                await emby_ep.timeline(
                                                    plex_ep.convertTime(plex_ep.viewOffset))
                                                log.info(
                                            f'{media.title}.{plex_ep.pretty_ep_out()}：Emby已同步进度')
                                            elif int(plex_ep.viewOffset)*10000 - \
                                                emby_ep.PlaybackPositionTicks < 0:
                                                await plex_ep.timeline(emby_ep.convertTime(
                                                    emby_ep.PlaybackPositionTicks))
                                                log.info(
                                            f'{media.title}.{plex_ep.pretty_ep_out()}：Plex已同步进度')
                                        #情况4：plex未观看，emby观看
                                        elif not plex_ep.viewCount and emby_ep.Played:
                                            await plex_ep.watched()
                                            log.info(
                                            f'{media.title}.{plex_ep.pretty_ep_out()}：Plex已观看')
                                        #情况5：都未观看
                                        elif not plex_ep.viewCount and not emby_ep.Played:
                                            log.info(
                                            f'{media.title}.{plex_ep.pretty_ep_out()}：Plex,Emby都未观看')
                                        #其余情况放入报错日志待议
                                        else:
                                            log.error(
                                        f'someting wrong:{media.title}.{plex_ep.pretty_ep_out()},plex:-{plex_ep.viewCount}-{plex_ep.viewOffset},emby:-{emby_ep.Played}-{emby_ep.PlaybackPositionTicks}')
                                        #移除匹配成功集数
                                        emby_eps.remove(emby_ep)
                                        break
                                #集数匹配失败
                                if not exist:
                                    log.info(f'{media.title}.{plex_ep.pretty_ep_out()}:：未在Emby中存在')
                            #匹配完后，emby的集数有残留，plex未存在
                            if emby_eps:
                                for emby_ep in emby_eps:
                                    log.info(f'{media.title}.{emby_ep.pretty_ep_out()}:：未在Plex中存在')
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            except:
                log.error(f'{media.title}\{emby_media.Name}同步失败 ：\n {traceback.format_exc()}')

    async def synctask(self):
        log.info(f"开始同步plex({self.plex.name})，emby({self.plex.name})全部观看历史")
        try:
            tasks = set()
            library = await self.plex.library()
            sections = library.sections()
            for section in sections:
                data = await section.all()
                for media in data:
                    future = asyncio.create_task(self._synctask(media=media))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"同步plex({self.plex.name})，emby({self.plex.name})全部观看历史完毕")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'同步plex({self.plex.name})，emby({self.plex.name})全部观看历史失败 ：\n {traceback.format_exc()}')

    async def _plex_sync_emby(self,media):
        try:
            #判断是电视剧还是电影，通过id来匹配
            if isinstance(media,Episode):
                p_media = await media.GetShow()
                emby_medias = await self.emby.guidsearch(tmdb=p_media.tmdbid,imdb=p_media.imdbid,tvdb=p_media.tvdbid)
            elif isinstance(media,Movie):
                await media.fetchitem()
                emby_medias = await self.emby.guidsearch(tmdb=media.tmdbid,imdb=media.imdbid,tvdb=media.tvdbid)
            #判断是否存在该影视
            if emby_medias:
                for emby_media in emby_medias:
                    #情况1：电影
                    if isinstance(media,Movie) and isinstance(emby_media,embyserver.Movie):
                        #对于plex，若存在viewedAt参数说明已观看
                        if media.viewedAt:
                            await emby_media.watched()
                            #刷新重载媒体数据
                            await emby_media.reload()
                            #刷新Task的emby最新已观看时间戳
                            async with self.lock:
                                if self.last_vieweddate < emby_media.LastPlayedDate:
                                    self.last_vieweddate = emby_media.LastPlayedDate
                                if media.viewedAt - self.last_viewed > 0:
                                    self.last_viewed = media.viewedAt
                            log.info(f'Emby服务器已观看：{media.title}')
                        #继续观看的情况：
                        elif media.lastViewedAt:
                            await emby_media.timeline(media.convertTime(media.viewOffset))
                            await emby_media.reload()
                            #刷新Task的emby最新继续观看时间戳
                            async with self.lock:
                                if self.last_viewingdate < emby_media.LastPlayedDate:
                                    self.last_viewingdate = emby_media.LastPlayedDate
                                if media.lastViewedAt - self.last_viewing > 0:
                                    self.last_viewing = media.lastViewedAt
                            log.info(f'Emby服务器已同步进度：{media.title}')
                    #情况2：剧集
                    elif isinstance(media,Episode) and isinstance(emby_media,embyserver.Show):
                        se_num = media.parentIndex
                        ep_num = media.index
                        #获取到对应集数
                        emby_ep = await emby_media.episode(se_num,ep_num)
                        #判断是否存在
                        if emby_ep:
                            #1.已观看
                            if media.viewedAt:
                                await emby_ep.watched()
                                await emby_ep.reload()
                                async with self.lock:
                                    if self.last_vieweddate < emby_ep.LastPlayedDate:
                                        self.last_vieweddate = emby_ep.LastPlayedDate
                                    if media.viewedAt - self.last_viewed > 0:
                                        self.last_viewed = media.viewedAt
                                log.info(f'{p_media.title}.{media.pretty_ep_out()}：Emby已观看')
                            #2.继续观看
                            elif media.lastViewedAt:
                                await emby_ep.timeline(media.convertTime(media.viewOffset))
                                await emby_ep.reload()
                                async with self.lock:
                                    if self.last_viewingdate < emby_ep.LastPlayedDate:
                                        self.last_viewingdate = emby_ep.LastPlayedDate
                                    if media.lastViewedAt - self.last_viewing > 0:
                                        self.last_viewing = media.lastViewedAt
                                log.info(f'{p_media.title}.{media.pretty_ep_out()}：Emby已同步进度')
                        else:
                            log.warning(f'{p_media.title}.{media.pretty_ep_out()}：Emby无该集')
            else:
                log.warning(f'{p_media.title}：Emby无该影视')
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'Plex同步Emby播放进度失败{media.title} ：\n {traceback.format_exc()}')

    async def _emby_sync_plex(self,media):
        try:
            if isinstance(media,embyserver.Episode):
                p_media = await media.GetShow()
                plex_medias = await self.plex.guidsearch(tmdb=p_media.tmdbid,imdb=p_media.imdbid,tvdb=p_media.tvdbid)
            elif isinstance(media,embyserver.Movie):
                plex_medias = await self.plex.guidsearch(tmdb=media.tmdbid,imdb=media.imdbid,tvdb=media.tvdbid)

            if plex_medias:
                for plex_media in plex_medias:
                    if isinstance(media,embyserver.Movie) and isinstance(plex_media,Movie):
                        if media.PlaybackPositionTicks:
                            await plex_media.timeline(media.convertTime(media.PlaybackPositionTicks))
                            await plex_media.fetchitem()
                            async with self.lock:
                                if plex_media.lastViewedAt - self.last_viewing  > 0:
                                    self.last_viewing = plex_media.lastViewedAt
                                if media.LastPlayedDate > self.last_viewingdate:
                                    self.last_viewingdate = media.LastPlayedDate
                            log.info(f'Plex服务器已同步进度：{media.Name}')
                        elif media.Played:
                            await plex_media.watched()
                            await plex_media.fetchitem()
                            async with self.lock:
                                if plex_media.lastViewedAt - self.last_viewed  > 0:
                                    self.last_viewed = plex_media.lastViewedAt
                                if media.LastPlayedDate > self.last_vieweddate:
                                    self.last_vieweddate = media.LastPlayedDate
                            log.info(f'Plex服务器已观看：{media.Name}')
                    elif isinstance(media,embyserver.Episode) and isinstance(plex_media,Show):
                        se_num = media.ParentIndexNumber
                        ep_num = media.IndexNumber
                        plex_ep = await plex_media.episode(se_num,ep_num)
                        if plex_ep:
                            if media.PlaybackPositionTicks:
                                await plex_ep.timeline(media.convertTime(media.PlaybackPositionTicks))
                                await plex_media.fetchitem()
                                async with self.lock:
                                    if plex_media.lastViewedAt - self.last_viewing  > 0:
                                        self.last_viewing = plex_media.lastViewedAt
                                    if media.LastPlayedDate > self.last_viewingdate:
                                        self.last_viewingdate = media.LastPlayedDate
                                log.info(f'{p_media.Name}.{media.pretty_ep_out()}：Plex已同步进度')
                            elif media.Played:
                                await plex_ep.watched()
                                await plex_media.fetchitem()
                                async with self.lock:
                                    if plex_media.lastViewedAt - self.last_viewed  > 0:
                                        self.last_viewed = plex_media.lastViewedAt
                                    if media.LastPlayedDate > self.last_vieweddate:
                                        self.last_vieweddate = media.LastPlayedDate
                                log.info(f'{p_media.Name}.{media.pretty_ep_out()}：Plex已观看')
                        else:
                            log.warning(f'{p_media.Name}.{media.pretty_ep_out()}：Plex无该集')
            else:
                log.warning(f'{p_media.Name}：Plex无该影视')
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'Emby同步Plex播放进度失败{media.Name} ：\n {traceback.format_exc()}')
    
    async def cronsync(self):
        try:
            log.info(f'{self.plex.name} / {self.emby.name}：开始同步进度')
            tasks = set()
            #获取plex，emby最近观看记录和继续观看
            plex_history = await self.plex.history()
            plex_cont = await self.plex.hub_continue()
            emby_history = await self.emby.history()
            emby_cont = await self.emby.hub_continue()
            #初始化参数
            async with self.lock:
                if not hasattr(self,'last_viewing'):
                    #plex最新继续观看时间戳
                    self.last_viewing = plex_cont[0].lastViewedAt
                if not hasattr(self,'last_viewed'):
                    if not plex_history[0].viewedAt:
                        self.last_viewed = plex_history[0].lastViewedAt
                    else:
                        self.last_viewed = plex_history[0].viewedAt
                if not hasattr(self,'last_viewingdate'):
                    #emby最新继续观看时间戳
                    self.last_viewingdate = emby_cont[0].LastPlayedDate
                if not hasattr(self,'last_vieweddate'):
                    #emby最新已观看时间戳
                    self.last_vieweddate = emby_history[0].LastPlayedDate
            #递归判断,所有新增plex继续观看
            for _cont in plex_cont:
                if _cont.lastViewedAt - self.last_viewing > 0:
                    future = asyncio.create_task(self._plex_sync_emby(media=_cont))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
                else:
                    break
            #所有新增plex已观看
            for _his in plex_history:
                if not _his.viewedAt:
                    _his.viewedAt = _his.lastViewedAt
                if _his.viewedAt - self.last_viewed > 0:
                    future = asyncio.create_task(self._plex_sync_emby(media=_his))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
                else:
                    break
            #所有新增emby已观看
            for _his in emby_history:
                if _his.LastPlayedDate > self.last_vieweddate:
                    future = asyncio.create_task(self._emby_sync_plex(media=_his))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
                else:
                    break
            #所有新增emby继续观看
            for _cont in emby_cont:
                if _cont.LastPlayedDate > self.last_viewingdate:
                    future = asyncio.create_task(self._emby_sync_plex(media=_cont))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
                else:
                    break
            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"{self.plex.name} / {self.emby.name}：同步进度完毕，等待下一次运行")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{self.plex.name} / {self.emby.name}同步进度失败 ：\n {traceback.format_exc()}')