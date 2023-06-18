import asyncio
import traceback
import aiohttp
import embyserver
from log import log
from pypinyin import pinyin, Style
from plexserver import Plexserver,Show,Movie,Episode
from embyserver import Embyserver
from conf import PROXY,ISPROXY,TMDB_API,CONCURRENT_NUM

class Task():
    def __init__(self,plex:Plexserver=None,emby:Embyserver=None) -> None:
        self.plex = plex
        self.emby = emby

    async def init(self):
        self.sem = asyncio.Semaphore(CONCURRENT_NUM)
        self.library = await self.plex.library()
        self.sections = self.library.sections()
        if not hasattr(self,'session'):
            self.session = aiohttp.ClientSession()
    
    async def _roletask(self,media,tasks):
        try:
            async with self.sem:
                if not media.tmdbid:
                    log.warning(media.title+': 未找到该条目tmdb ID')
                else:
                    if media.type == 'show':
                        url = f'https://api.themoviedb.org/3/tv/{media.tmdbid}/aggregate_credits?api_key={TMDB_API}&language=zh-CN'
                    elif media.type == 'movie':
                        url = f'https://api.themoviedb.org/3/movie/{media.tmdbid}/credits?api_key={TMDB_API}&language=zh-CN'
                    else:
                        log.warning('只支持电影和剧集')
                        return
                    for _ in range(3):
                        try:
                            if ISPROXY:
                                async with self.session.get(url,proxy=PROXY) as res:
                                    if res.status == 200:
                                        tmdb_data = await res.json()
                            else:
                                async with self.session.get(url) as res:
                                    if res.status == 200:
                                        tmdb_data = await res.json()
                        except:
                            log.error('连接失败，正在重试...')
                            await asyncio.sleep(1)
                    cast_dir = {}
                    for cast in tmdb_data['cast']:
                        if cast['known_for_department'] == 'Acting':
                            cast_dir[f'{cast["name"]}'] = cast['id']
                    roles = media.roles()
                    actor = []
                    for role in roles:
                        if not role.check_chs(role.tag):
                            if cast_dir.get(role.tag,None):
                                cid = cast_dir.get(role.tag)
                                chsdir = await role.request_tmdb(self.session,cid)
                                if chsdir['chs']:
                                    chsname = chsdir['chs']
                                    log.info(f'{media.title}: {role.tag} ------> {chsname}')
                                    role.tag = chsname
                                    actor.append(role)
                                else:
                                    log.info(f'{media.title}: {role.tag} 暂无中文数据')
                                    actor.append(role)
                            else:
                                log.warning(f'{media.title}: {role.tag} 未发现该演员在该影视tmdb条目中')
                                actor.append(role)
                        else:
                            log.info(f'{media.title}: {role.tag} 此演员已有中文数据')
                            actor.append(role)
                    await media.edit_role(actor)
                    log.info(media.title+': 修改完毕')
        except:
            log.critical(traceback.format_exc())
        finally:
            tasks.remove(asyncio.current_task())

    async def _sorttask(self,media,tasks):
        try:
            async with self.sem:
                if media.titleSort is None:
                    convert = pinyin(media.formatchs(media.title),style=Style(4))
                    titlevalue = str.join('',list(map(lambda x:x[0],convert)))
                    await media.edit_titlesort(titlevalue,lock=1)
                    log.info(f'{media.title}: 改变标题排序为 {titlevalue}')
                else:
                    convert = pinyin(media.formatchs(media.title),style=Style(4))
                    titlevalue = str.join('',list(map(lambda x:x[0],convert)))
                    if titlevalue == media.titleSort:
                        log.info(f'{media.title}: 已经存在标题排序{titlevalue}')
                    else:
                        await media.edit_titlesort(titlevalue,lock=1)
                        log.info(f'{media.title}: 改变标题排序为 {titlevalue}')
        except:
            log.critical(traceback.format_exc())
        finally:
            tasks.remove(asyncio.current_task())

    async def _synctask(self,media,tasks):
        try:
            async with self.sem:
                if not media.tmdb:
                    log.warning(media.title+': 未找到该条目tmdb ID')
                else:
                    emby_medias = await self.emby.guidsearch(media.tmdb)
                    if not emby_medias:
                        log.info(f'Emby服务器未找到：{media.title}')
                        return
                for emby_media in emby_medias:
                    if isinstance(media,Movie) and emby_media.Type.lower() == 'movie':
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
                            if emby_media.PlaybackPositionTicks != 0:
                                await media.timeline(emby_media.convertTime(
                                    emby_media.PlaybackPositionTicks))
                                log.info(f'Plex服务器已同步进度：{media.title}')
                            elif emby_media.Played:
                                await media.watched()
                                log.info(f'Plex服务器已观看：{media.title}')

                    elif isinstance(media,Show) and emby_media.Type.lower() == 'series':
                        for emby_media in emby_medias:
                            emby_eps = await emby_media.episodes()
                            if media.viewCount or emby_media.check_played():
                                plex_eps = await media.episodes()
                                for plex_ep in plex_eps:
                                    exist = False
                                    for emby_ep in emby_eps:
                                        if plex_ep.parentIndex == emby_ep.ParentIndexNumber \
                                            and plex_ep.index == emby_ep.IndexNumber:
                                            exist = True
                                            if plex_ep.viewCount and emby_ep.Played:
                                                pass
                                            elif plex_ep.viewCount and not emby_ep.Played:
                                                await emby_ep.watched()
                                                log.info(
                                                f'{media.title}.{plex_ep.pretty_ep_out()}：Emby已观看')
                                            elif plex_ep.viewOffset or emby_ep.PlaybackPositionTicks != 0:
                                                if plex_ep.viewOffset is None:
                                                    plex_ep.viewOffset = 0
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
                                            elif not plex_ep.viewCount and emby_ep.Played:
                                                await plex_ep.watched()
                                                log.info(
                                                f'{media.title}.{plex_ep.pretty_ep_out()}：Plex已观看')
                                            elif not plex_ep.viewCount and not emby_ep.Played:
                                                log.info(
                                                f'{media.title}.{plex_ep.pretty_ep_out()}：Plex,Emby都未观看')
                                            else:
                                                log.warning(
                                            f'someting wrong:{media.title}.{plex_ep.pretty_ep_out()},plex:-{plex_ep.viewCount}-{plex_ep.viewOffset},emby:-{emby_ep.Played}-{emby_ep.PlaybackPositionTicks}')
                                            emby_eps.remove(emby_ep)
                                    if not exist:
                                        log.info(f'{media.title}.{plex_ep.pretty_ep_out()}:：未在Emby中存在')
                                if emby_eps:
                                    for emby_ep in emby_eps:
                                        log.info(f'{media.title}.{emby_ep.pretty_ep_out()}:：未在Plex中存在')
        except:
            log.critical(traceback.format_exc())
        finally:
            tasks.remove(asyncio.current_task())

    async def _plex_sync_emby(self,media,tasks):
        try:
            if isinstance(media,Episode):
                p_media = await media.GetShow()
                emby_medias = await self.emby.guidsearch(p_media.tmdb)
            elif isinstance(media,Movie):
                await media.fetchitem()
                emby_medias = await self.emby.guidsearch(media.tmdb)

            if emby_medias:
                for emby_media in emby_medias:
                    if isinstance(media,Movie) and emby_media.Type.lower() == 'movie':
                        if media.viewedAt:
                            await emby_media.watched()
                            await emby_media.fetchitem()
                            if self.last_vieweddate < emby_media.LastPlayedDate:
                                self.last_vieweddate = emby_media.LastPlayedDate
                            if media.viewedAt - self.last_viewed > 0:
                                self.last_viewed = media.viewedAt
                            log.info(f'Emby服务器已观看：{media.title}')
                        elif media.lastViewedAt:
                            await emby_media.timeline(media.convertTime(media.viewOffset))
                            await emby_media.fetchitem()
                            if self.last_viewingdate < emby_media.LastPlayedDate:
                                self.last_viewingdate = emby_media.LastPlayedDate
                            if media.lastViewedAt - self.last_viewing > 0:
                                self.last_viewing = media.lastViewedAt
                            log.info(f'Emby服务器已同步进度：{media.title}')
                    elif isinstance(media,Episode) and emby_media.Type.lower() == 'series':
                        se_num = media.parentIndex
                        ep_num = media.index
                        emby_ep = await emby_media.episode(se_num,ep_num)
                        if emby_ep:
                            if media.viewedAt:
                                await emby_ep.watched()
                                await emby_ep.reload()
                                if self.last_vieweddate < emby_ep.LastPlayedDate:
                                    self.last_vieweddate = emby_ep.LastPlayedDate
                                if media.viewedAt - self.last_viewed > 0:
                                    self.last_viewed = media.viewedAt
                                log.info(f'{p_media.title}.{media.pretty_ep_out()}：Emby已观看')
                            elif media.lastViewedAt:
                                await emby_ep.timeline(media.convertTime(media.viewOffset))
                                await emby_ep.reload()
                                if self.last_viewingdate < emby_ep.LastPlayedDate:
                                    self.last_viewingdate = emby_ep.LastPlayedDate
                                if media.lastViewedAt - self.last_viewing > 0:
                                    self.last_viewing = media.lastViewedAt
                                log.info(f'{p_media.title}.{media.pretty_ep_out()}：Emby已同步进度')
                        else:
                            log.warning(f'{p_media.title}.{media.pretty_ep_out()}：Emby无该集')
            else:
                log.warning(f'{p_media.title}：Emby无该影视')
        except:
            log.critical(traceback.format_exc())
        finally:
            tasks.remove(asyncio.current_task())

    async def _emby_sync_plex(self,media,tasks):
        try:
            if isinstance(media,embyserver.Episode):
                p_media = await media.GetShow()
                plex_medias = await self.plex.guidsearch(p_media.tmdb)
            elif isinstance(media,embyserver.Movie):
                await media.fetchitem()
                plex_medias = await self.plex.guidsearch(media.tmdb)

            if plex_medias:
                for plex_media in plex_medias:
                    if isinstance(media,embyserver.Movie) and plex_media.type.lower() == 'movie':
                        if media.PlaybackPositionTicks:
                            await plex_media.timeline(media.convertTime(media.PlaybackPositionTicks))
                            await plex_media.fetchitem()
                            if plex_media.lastViewedAt - self.last_viewing  > 0:
                                self.last_viewing = plex_media.lastViewedAt
                            if media.LastPlayedDate > self.last_viewingdate:
                                self.last_viewingdate = media.LastPlayedDate
                            log.info(f'Plex服务器已同步进度：{media.Name}')
                        elif media.Played:
                            await plex_media.watched()
                            await plex_media.fetchitem()
                            if plex_media.lastViewedAt - self.last_viewed  > 0:
                                self.last_viewed = plex_media.lastViewedAt
                            if media.LastPlayedDate > self.last_vieweddate:
                                self.last_vieweddate = media.LastPlayedDate
                            log.info(f'Plex服务器已观看：{media.Name}')
                    elif isinstance(media,embyserver.Episode) and plex_media.type.lower() == 'show':
                        se_num = media.ParentIndexNumber
                        ep_num = media.IndexNumber
                        plex_ep = await plex_media.episode(se_num,ep_num)
                        if plex_ep:
                            if media.PlaybackPositionTicks:
                                await plex_ep.timeline(media.convertTime(media.PlaybackPositionTicks))
                                await plex_media.fetchitem()
                                if plex_media.lastViewedAt - self.last_viewing  > 0:
                                    self.last_viewing = plex_media.lastViewedAt
                                if media.LastPlayedDate > self.last_viewingdate:
                                    self.last_viewingdate = media.LastPlayedDate
                                log.info(f'{p_media.Name}.{media.pretty_ep_out()}：Plex已同步进度')
                            elif media.Played:
                                await plex_ep.watched()
                                await plex_media.fetchitem()
                                if plex_media.lastViewedAt - self.last_viewed  > 0:
                                    self.last_viewed = plex_media.lastViewedAt
                                if media.LastPlayedDate > self.last_vieweddate:
                                    self.last_vieweddate = media.LastPlayedDate
                                log.info(f'{p_media.Name}.{media.pretty_ep_out()}：Plex已观看')
                        else:
                            log.warning(f'{p_media.Name}.{media.pretty_ep_out()}：Plex无该集')
            else:
                log.warning(f'{p_media.Name}：Plex无该影视')
        except:
            log.critical(traceback.format_exc())
        finally:
            tasks.remove(asyncio.current_task())

    #async def _emby_role(self,media,tasks)

    async def basetask(self,method):
        tasks = []
        self.medias = []
        for section in self.sections:
                data = await section.all()
                for media in data:
                    await media.fetchitem()
                    self.medias.append(media)
        try:
            for media in self.medias:
                task = asyncio.create_task(method(media=media,tasks=tasks))
                tasks.append(task)

            for task in asyncio.as_completed(tasks):
                await task
        except:
            log.critical(traceback.format_exc())

    async def sorttask(self):
        await self.basetask(self._sorttask)
        #return sort_tasks

    async def roletask(self):
        await self.basetask(self._roletask)
        #return role_tasks

    async def synctask(self):
        await self.basetask(self._synctask)

    async def embyrole(self):
        await self.basetask(self._emby_role)

    async def cronsync(self):
        try:
            log.info('开始同步进度')
            tasks = []
            plex_history = await self.plex.history()
            plex_cont = await self.plex.hub_continue()
            emby_history = await self.emby.history()
            emby_cont = await self.emby.hub_continue()
            if not hasattr(self,'last_viewing'):
                self.last_viewing = plex_cont[0].lastViewedAt
            if not hasattr(self,'last_viewed'):
                if not plex_history[0].viewedAt:
                    self.last_viewed = plex_history[0].lastViewedAt
                else:
                    self.last_viewed = plex_history[0].viewedAt
            if not hasattr(self,'last_viewingdate'):
                self.last_viewingdate = emby_cont[0].LastPlayedDate
            if not hasattr(self,'last_vieweddate'):
                self.last_vieweddate = emby_history[0].LastPlayedDate

            for _cont in plex_cont:
                if _cont.lastViewedAt - self.last_viewing > 0:
                    task = asyncio.create_task(self._plex_sync_emby(media=_cont,tasks=tasks))
                    tasks.append(task)
                else:
                    break
            
            for _his in plex_history:
                if not _his.viewedAt:
                    _his.viewedAt = _his.lastViewedAt
                if _his.viewedAt - self.last_viewed > 0:
                    task = asyncio.create_task(self._plex_sync_emby(media=_his,tasks=tasks))
                    tasks.append(task)
                else:
                    break
            
            for _his in emby_history:
                if _his.LastPlayedDate > self.last_vieweddate:
                    task = asyncio.create_task(self._emby_sync_plex(media=_his,tasks=tasks))
                    tasks.append(task)
                else:
                    break
            
            for _cont in emby_cont:
                if _cont.LastPlayedDate > self.last_viewingdate:
                    task = asyncio.create_task(self._emby_sync_plex(media=_cont,tasks=tasks))
                    tasks.append(task)
                else:
                    break
            
            for task in asyncio.as_completed(tasks):
                await task
        except:
            log.critical(traceback.format_exc())
            
    async def close(self):
        await self.session.close()