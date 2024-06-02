import traceback
import asyncio
import time
import datetime
import server.embyserver as emby
import server.plexserver as plex
import server.jellyfinserver as jellyfin
from task.base import SyncTask as ST
from util.log import log
from util.exception import ServerTypeError,MediaTypeError

class SyncTask(ST):
    def __init__(self, task_info: dict, servers) -> None:
        super().__init__(task_info, servers)

    def check_offset(self,time1,time2,sync_type):
        if sync_type == 0:
            return time1 - time2
        elif sync_type == 1:
            return int(time1)*10000 - time2
        elif sync_type == 2:
            return time1 - time2

    def check_match_ep(self,ep,match_ep,sync_type):
        if sync_type == 0:
            if ep.ParentIndexNumber == match_ep.ParentIndexNumber and \
                ep.IndexNumber == match_ep.IndexNumber:
                return True
            else:
                return False
        elif sync_type == 1:
            if ep.parentIndex == match_ep.ParentIndexNumber and\
                ep.index == match_ep.IndexNumber:
                return True
            else:
                return False
        elif sync_type == 2:
            if ep.parentIndex == match_ep.parentIndex and\
                ep.index == match_ep.index:
                return True
            else:
                return False
 
    def convert_type_status(self,media,match_media,sync_type):
        if sync_type == 0:
            media_played = media.Played
            match_media_played = match_media.Played
            media_playing = media.PlaybackPositionTicks if media.PlaybackPositionTicks != 0 else None
            match_media_playing = match_media.PlaybackPositionTicks if media.PlaybackPositionTicks != 0 else None
        elif sync_type == 1:
            media_played = media.viewCount
            media_playing = media.viewOffset
            match_media_played = match_media.Played
            match_media_playing = match_media.PlaybackPositionTicks
        elif sync_type == 2:
            media_played = media.viewCount
            media_playing = media.viewOffset
            match_media_played = match_media.viewCount
            match_media_playing = match_media.viewOffset
        return media_played,media_playing,match_media_played,match_media_playing

    def renew_date(self,playdate,match_playdate,status,reverse:bool):
        if status == 'played':
            if reverse:
                if self.server2_viewed < playdate:
                    self.server2_viewed = playdate
                if self.server1_viewed < match_playdate:
                    self.server1_viewed = match_playdate
            else:
                if self.server2_viewed < match_playdate:
                    self.server2_viewed = match_playdate
                if  self.server1_viewed < playdate:
                    self.server1_viewed = playdate
        elif status == 'playing':
            if reverse:
                if self.server1_viewing < match_playdate:
                    self.server1_viewing = match_playdate
                if self.server2_viewing < playdate:
                    self.server2_viewing = playdate
            else:
                if self.server1_viewing < playdate:
                    self.server1_viewing = playdate
                if self.server2_viewing < match_playdate:
                    self.server2_viewing = match_playdate

    async def sync_movie(self,media,match_media,server1_name,server2_name,sync_type):
        #电影同步
        media_played,media_playing,match_media_played,match_media_playing = self.convert_type_status(
                                                                            media,match_media,sync_type)
        if sync_type == 0:
            name = media.Name
        else:
            name = media.title
        if media_played or media_playing:
            if media_played and match_media_played:
                pass
            elif media_played and not match_media_played:
                await match_media.watched()
                log.info(f'{server2_name}服务器已观看：{name}')
            elif media_playing or match_media_playing:
                offset = self.check_offset(media_playing,match_media_playing,sync_type)
                if offset > 0:
                    await match_media.timeline(
                        media.convertTime(media_playing,sync_type))
                    log.info(f'{server2_name}服务器已同步进度：{name}')
                elif offset < 0:
                    await media.timeline(match_media.convertTime(
                        match_media_playing,sync_type))
                    log.info(f'{server1_name}服务器已同步进度：{name}')
            elif not media_played and match_media_played:
                await media.watched()
                log.info(f'{server1_name}服务器已观看：{name}')
            else:
                log.warning(f'someting wrong:{name}')
        else:
            if match_media_playing:
                await media.timeline(match_media.convertTime(
                    match_media_playing,sync_type))
                log.info(f'{server1_name}服务器已同步进度：{name}')
            elif match_media_played:
                await media.watched()
                log.info(f'{server1_name}服务器已观看：{name}')

    async def sync_show(self,media,match_media,server1_name,server2_name,sync_type):
        match_eps = await match_media.episodes()
        eps = await media.episodes()
        if sync_type == 0:
            show_played = media.check_played()
            match_show_played = match_media.check_played()
            name = media.Name
            match_name = match_media.Name
        elif sync_type == 1:
            show_played = media.viewCount
            match_show_played = match_media.check_played()
            name = media.title
            match_name = match_media.Name
        elif sync_type == 2:
            show_played = media.viewCount
            match_show_played = match_media.viewCount
            name = media.title
        if show_played or match_show_played:
            for ep in eps:
                exist = False
                for match_ep in match_eps:
                    if self.check_match_ep(ep,match_ep,sync_type):
                        exist = True
                        media_played,media_playing,match_media_played,match_media_playing = self.convert_type_status(
                                                                            ep,match_ep,sync_type)
                        if media_played and match_media_played:
                            pass
                        elif media_played and not match_media_played:
                            await match_ep.watched()
                            log.info(f'{name}.{ep.pretty_ep_out()}：{server2_name}已观看')
                        elif media_playing or match_media_playing:
                            offset = self.check_offset(media_playing,match_media_playing,sync_type)
                            if offset > 0:
                                await match_media.timeline(
                                media.convertTime(media_playing,sync_type))
                                log.info(f'{name}.{ep.pretty_ep_out()}：{server2_name}已同步进度')
                            elif offset < 0:
                                await media.timeline(match_media.convertTime(
                                    match_media_playing,sync_type))
                                log.info(f'{name}.{ep.pretty_ep_out()}：{server1_name}已同步进度')
                        elif not media_played and match_media_played:
                            log.info(f'{name}.{ep.pretty_ep_out()}：{server1_name}已观看')
                        elif not media_played and not match_media_played:
                            log.info(f'{name}.{ep.pretty_ep_out()}：{server1_name},{server2_name}都未观看')
                        else:
                            log.warning(f'someting wrong:{name}.{ep.pretty_ep_out()},\
                                      {server1_name}:-{media_played}-{media_playing},\
                                      {server2_name}:-{match_media_played}-{match_media_playing}')
                        match_eps.remove(match_ep)
                        break
                if exist == False:
                    log.info(f'{name}.{ep.pretty_ep_out()}:：未在{server2_name}中存在')
            if match_eps:
                for eps in match_eps:
                    log.info(f'{name}.{match_ep.pretty_ep_out()}:：未在{server1_name}中存在')

    async def _synctask(self,server1,server2,media,sync_type):
        async with server1.sem:
            try:
                await media.fetchitem()
                server1_name = f'{server1.type.title()}({server1.name})'
                server2_name = f'{server2.type.title()}({server2.name})'
                if sync_type == 0:
                    guid = media.ProviderIds
                    name = media.Name
                    Server1_Movie = Server2_Movie = (emby.Movie,jellyfin.Movie)
                    Server1_Show = Server2_Show = (emby.Show,jellyfin.Show)
                else:
                    guid = media.guid
                    name = media.title
                    Server1_Movie = plex.Movie
                    Server1_Show = plex.Show
                    Server2_Movie = (emby.Movie,jellyfin.Movie)
                    Server2_Show = (emby.Show,jellyfin.Show)
                if not guid:
                    log.warning(name+': 未找到该条目任何刮削ID，请检查刮削')
                    return 0
                medias = await server2.guidsearch(tmdb=media.tmdbid,imdb=media.imdbid,tvdb=media.tvdbid)
                if not medias:
                    log.info(f'{server2_name}服务器未找到：{name}')
                    return
                for match_media in medias:
                    #电影同步
                    if isinstance(media,Server1_Movie) and isinstance(match_media,Server2_Movie):
                        await self.sync_movie(media,match_media,server1_name,server2_name,sync_type)
                    #剧集同步
                    elif isinstance(media,Server1_Show) and isinstance(match_media,Server2_Show):
                        await self.sync_show(media,match_media,server1_name,server2_name,sync_type)
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            except:
                log.error(f'{name}\{match_media.Name}同步失败 ：\n {traceback.format_exc()}')

    async def synctask(self):
        if self.plex == None:
            server1 = self.emby
            server2 = self.jellyfin
            sync_type = 0
            # 0 without plex, 1 with plex, 2 with 2plex
        elif self.plex2 != None:
            server1 = self.plex
            server2 = self.plex2
            sync_type = 2
        elif self.jellyfin == None:
            server1 = self.plex
            server2 = self.emby
            sync_type = 1
        elif self.emby == None:
            server1 = self.plex
            server2 = self.jellyfin
            sync_type = 1
        else:
            raise ServerTypeError(f"{self.name}： 请选择正确的同步组合")
        log.info(f"开始同步{server1.type.title()}({server1.name})，{server2.type.title()}({server2.name})全部观看历史")
        try:
            tasks = set()
            if sync_type in (1,2):
                library = await server1.library()
                sections = library.sections()
            else:
                sections = await server1.library()
            for section in sections:
                try:
                    data = await section.all()
                    for media in data:
                        future = asyncio.create_task(self._synctask(media=media,server1=server1
                                                                    ,server2=server2,sync_type=sync_type))
                        future.add_done_callback(tasks.discard)
                        tasks.add(future)
                except MediaTypeError:
                    continue
            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"同步{server1.type.title()}({server1.name})，{server2.type.title()}({server2.name})全部观看历史完毕")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'同步{server1.type.title()}({server1.name})，{server2.type.title()}({server2.name})全部观看历史失败 ：\n {traceback.format_exc()}')

    async def _cronsync(self,server1,server2,media,sync_type,reverse:bool=False):
        #media_type:emby,jellyfin,plex:string
        media_type = None
        try:
            if isinstance(media,(emby.Episode,jellyfin.Episode,plex.Episode)):
                server1_media = await media.GetShow()
                server2_medias = await server2.guidsearch(tmdb=server1_media.tmdbid,imdb=server1_media.imdbid,tvdb=server1_media.tvdbid)
                media_type = 'ep'
            elif isinstance(media,(emby.Movie,jellyfin.Movie,plex.Movie)):
                if server1.type == 'plex':
                    await media.fetchitem()
                server2_medias = await server2.guidsearch(tmdb=media.tmdbid,imdb=media.imdbid,tvdb=media.tvdbid)
                media_type = 'movie'
            server1_name = f'{server1.type.title()}({server1.name})'
            server2_name = f'{server2.type.title()}({server2.name})'
            if sync_type == 0:
                media_played = media.Played
                media_playing = media.PlaybackPositionTicks if media.PlaybackPositionTicks != 0 else None
                if media_type == 'movie':
                    name = media.Name
                else:
                    name = server1_media.Name
            elif sync_type == 1:
                if server1.type == 'plex':
                    media_played = media.viewCount
                    media_playing = media.viewOffset
                    if media_type == 'movie':
                        name = media.title
                    else:
                        name = server1_media.title
                else:
                    media_played = media.Played
                    media_playing = media.PlaybackPositionTicks if media.PlaybackPositionTicks != 0 else None
                    if media_type == 'movie':
                        name = media.Name
                    else:
                        name = server1_media.Name
            elif sync_type == 2:
                media_played = media.viewCount
                media_playing = media.viewOffset
                if media_type == 'movie':
                    name = media.title
                else:
                    name = server1_media.title
            match_medias = []
            if server2_medias:
                for match_media in server2_medias:
                    await asyncio.sleep(1)
                    if media_type == None:
                        raise
                    elif media_type == 'movie':
                        if isinstance(match_media,(emby.Movie,jellyfin.Movie,plex.Movie)):
                            match_medias.append(match_media)
                    elif media_type == 'ep':
                        if isinstance(match_media,(emby.Show,jellyfin.Show,plex.Show)):
                            match_medias.append(match_media)
            if match_medias:
                for match_media in match_medias:        
                    if media_type == None:
                        raise
                    elif media_type == 'movie':
                        if media_played:
                            await match_media.watched()
                            await match_media.reload()
                            async with self.lock:
                                if sync_type == 0:
                                    match_playdate = match_media.LastPlayedDate
                                    playdate = media.LastPlayedDate
                                elif sync_type == 1:
                                    if server1.type == 'plex':
                                        match_playdate = match_media.LastPlayedDate
                                        playdate = media.viewedAt
                                    else:
                                        match_playdate = match_media.viewedAt
                                        playdate = media.LastPlayedDate
                                elif sync_type == 2:
                                    match_playdate = match_media.viewedAt
                                    playdate = media.viewedAt
                                self.renew_date(playdate,match_playdate,'played',reverse)
                            log.info(f'{server2_name}服务器已观看：{name}')
                        elif media_playing:
                            await match_media.timeline(media.convertTime(media_playing,sync_type))
                            await match_media.reload()
                            async with self.lock:
                                if sync_type == 0:
                                    match_playingdate = match_media.LastPlayedDate
                                    playingdate = media.LastPlayedDate
                                elif sync_type == 1:
                                    if server1.type == 'plex':
                                        match_playingdate = match_media.LastPlayedDate
                                        playingdate = media.lastViewedAt
                                    else:
                                        match_playingdate = match_media.lastViewedAt
                                        playingdate = media.LastPlayedDate
                                elif sync_type == 2:
                                    match_playingdate = match_media.viewedAt
                                    playingdate = media.lastViewedAt
                                self.renew_date(playingdate,match_playingdate,'playing',reverse)
                            log.info(f'{server2_name}服务器已同步进度：{name}')
                    elif media_type == 'ep':
                        if server1.type == 'plex':
                            se_num = media.parentIndex
                            ep_num = media.index
                        else:
                            se_num = media.ParentIndexNumber
                            ep_num = media.IndexNumber
                        server2_ep = await match_media.episode(se_num,ep_num)
                        if server2_ep:
                            if media_played:
                                await server2_ep.watched()
                                if server2.type == 'plex':
                                    await match_media.reload()
                                else:
                                    await server2_ep.reload()
                                async with self.lock:
                                    if sync_type == 0:
                                        match_playdate = server2_ep.LastPlayedDate
                                        playdate = media.LastPlayedDate
                                    elif sync_type == 1:
                                        if server1.type == 'plex':
                                            match_playdate = server2_ep.LastPlayedDate
                                            playdate = media.viewedAt
                                        else:
                                            match_playdate = match_media.lastViewedAt
                                            playdate = media.LastPlayedDate
                                    elif sync_type == 2:
                                        match_playdate = match_media.viewedAt
                                        playdate = media.lastViewedAt
                                    self.renew_date(playdate,match_playdate,'played',reverse)
                                log.info(f'{name}.{media.pretty_ep_out()}：{server2_name}已观看') 
                            elif media_playing:
                                await server2_ep.timeline(media.convertTime(media_playing,sync_type))
                                if server2.type == 'plex':
                                    await match_media.reload()
                                else:
                                    await server2_ep.reload()
                                async with self.lock:
                                    if sync_type == 0:
                                        match_playingdate = server2_ep.LastPlayedDate
                                        playingdate = media.LastPlayedDate
                                    elif sync_type == 1:
                                        if server1.type == 'plex':
                                            match_playingdate = server2_ep.LastPlayedDate
                                            playingdate = media.lastViewedAt
                                        else:
                                            match_playingdate = match_media.lastViewedAt
                                            playingdate = media.LastPlayedDate
                                    elif sync_type == 2:
                                        match_playingdate = match_media.lastViewedAt
                                        playingdate = media.lastViewedAt
                                    self.renew_date(playingdate,match_playingdate,'playing',reverse)
                                log.info(f'{name}.{media.pretty_ep_out()}：{server2_name}已同步进度') 
                        else:
                            log.warning(f'{server1_media.Name}.{media.pretty_ep_out()}：无该集')
            else:
                log.warning(f'{name}：{server2_name}无该影视')
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{server1_name}同步{server2_name}播放进度失败{name} ：\n {traceback.format_exc()}')     

    async def cronsync(self):
        try:
            if self.plex == None:
                server1 = self.emby
                server2 = self.jellyfin
                # 0 without plex, 1 with plex
                sync_type = 0
            elif self.plex2 != None:
                server1 = self.plex
                server2 = self.plex2
                sync_type = 2
            elif self.jellyfin == None:
                server1 = self.plex
                server2 = self.emby
                sync_type = 1
            elif self.emby == None:
                server1 = self.plex
                server2 = self.jellyfin
                sync_type = 1
            else:
                raise ServerTypeError(f"{self.name}： 请选择正确的同步组合")
            server1_name = f'{server1.type.title()}({server1.name})'
            server2_name = f'{server2.type.title()}({server2.name})'
            log.info(f'{server1_name} / {server2_name}：开始同步进度')
            tasks = set()
            #获取plex，emby最近观看记录和继续观看
            server1_history = await server1.history()
            server1_cont = await server1.hub_continue()
            server2_history = await server2.history()
            server2_cont = await server2.hub_continue()
            #初始化参数
            async with self.lock:
                if not hasattr(self,'server1_viewing'):
                    #plex最新继续观看时间戳
                    if sync_type in (1,2):
                        self.server1_viewing = server1_cont[0].lastViewedAt if server1_cont else int(time.time())
                    elif sync_type == 0:
                        self.server1_viewing = server1_cont[0].LastPlayedDate if server1_cont else datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
                if not hasattr(self,'server1_viewed'):
                    if sync_type in (1,2):
                        if server1_history:
                            if not server1_history[0].viewedAt:
                                self.server1_viewed = server1_history[0].lastViewedAt
                            else:
                                self.server1_viewed = server1_history[0].viewedAt
                        else:
                            self.server1_viewed = int(time.time())
                    else:
                        self.server1_viewed = server1_history[0].LastPlayedDate if server1_history else datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
                if not hasattr(self,'server2_viewing'):
                    #emby最新继续观看时间戳
                    if sync_type in (0,1):
                        self.server2_viewing = server2_cont[0].LastPlayedDate if server2_cont else datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
                    elif sync_type == 2:
                        self.server2_viewing = server2_cont[0].lastViewedAt if server2_cont else int(time.time())
                if not hasattr(self,'server2_viewed'):
                    #emby最新已观看时间戳
                    if sync_type in (0,1):
                        self.server2_viewed = server2_history[0].LastPlayedDate if server2_history else datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
                    elif sync_type == 2:
                        if server2_history:
                            if not server2_history[0].viewedAt:
                                self.server2_viewed = server2_history[0].lastViewedAt
                            else:
                                self.server2_viewed = server2_history[0].viewedAt
                        else:
                            self.server2_viewed = int(time.time())

            #递归判断,所有新增plex继续观看
            for _cont in server1_cont:
                if sync_type in (1,2):
                    if _cont.lastViewedAt - self.server1_viewing > 0:
                        future = asyncio.create_task(self._cronsync(server1,server2,_cont,sync_type,False))
                        future.add_done_callback(tasks.discard)
                        tasks.add(future)
                    else:
                        break
                else:
                    if _cont.LastPlayedDate > self.server2_viewing:
                        future = asyncio.create_task(self._cronsync(server1,server2,_cont,sync_type,False))
                        future.add_done_callback(tasks.discard)
                        tasks.add(future)
                    else:
                        break
            #所有新增plex已观看
            for _his in server1_history:
                if sync_type in (1,2):
                    if not _his.viewedAt:
                        _his.viewedAt = _his.lastViewedAt
                    if _his.viewedAt - self.server1_viewed > 0:
                        future = asyncio.create_task(self._cronsync(server1,server2,_his,sync_type,False))
                        future.add_done_callback(tasks.discard)
                        tasks.add(future)
                    else:
                        break
                else:
                    if _his.LastPlayedDate > self.server1_viewed:
                        future = asyncio.create_task(self._cronsync(server1,server2,_his,sync_type,False))
                        future.add_done_callback(tasks.discard)
                        tasks.add(future)
                    else:
                        break
            #所有新增emby已观看
            for _his in server2_history:
                if sync_type in (0,1):
                    media_viewed = _his.LastPlayedDate
                else:
                    if not _his.viewedAt:
                        media_viewed = _his.lastViewedAt
                    else:
                        media_viewed = _his.viewedAt
                if media_viewed > self.server2_viewed:
                    future = asyncio.create_task(self._cronsync(server2,server1,_his,sync_type,True))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
                else:
                    break
            #所有新增emby继续观看
            for _cont in server2_cont:
                if sync_type in (0,1):
                    media_viewing = _cont.LastPlayedDate
                else:
                    media_viewing = _cont.lastViewedAt
                if media_viewing > self.server2_viewing:
                    future = asyncio.create_task(self._cronsync(server2,server1,_cont,sync_type,True))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
                else:
                    break
            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"{server1_name} / {server2_name}：同步进度完毕，等待下一次运行")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{server1_name} / {server2_name}同步进度失败 ：\n {traceback.format_exc()}')