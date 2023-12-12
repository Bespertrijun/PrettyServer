import asyncio
import traceback
import aiohttp
import embyserver
from log import log
from pypinyin import pinyin, Style,load_phrases_dict
from apscheduler.triggers.cron import CronTrigger
from plexserver import Plexserver,Show,Movie,Episode
from embyserver import Embyserver
from conf import PROXY,ISPROXY,TMDB_API,CONCURRENT_NUM,PLEX_SACN_TASK,EMBY_SACN_TASK
#更新词典
load_phrases_dict({'九重天': [['j'], ['c'],['t']]})
load_phrases_dict({'神藏': [['s'], ['z']]})

class Task():
    def __init__(self,plex:Plexserver=None,emby:Embyserver=None) -> None:
        self.plex = plex
        self.emby = emby

    async def init(self):
        self.sem = asyncio.Semaphore(CONCURRENT_NUM)
        self.lock = asyncio.Lock()
        if not hasattr(self,'session'):
            self.session = aiohttp.ClientSession()
    
    async def _plexrole(self,media):
        async with self.sem:
            await media.fetchitem()
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

    async def _plexsort(self,media):
        async with self.sem:
            #await media.fetchitem()
            if media.titleSort is None:
                convert = pinyin(media.formatchs(media.title).strip("-"),style=Style(4))
                titlevalue = str.join('',list(map(lambda x:x[0],convert)))
                await media.edit_titlesort(titlevalue,lock=1)
                log.info(f'{media.title}: 改变标题排序为 {titlevalue}')
            else:
                convert = pinyin(media.formatchs(media.title).strip("-"),style=Style(4))
                titlevalue = str.join('',list(map(lambda x:x[0],convert)))
                if titlevalue == media.titleSort:
                    log.info(f'{media.title}: 已经存在标题排序{titlevalue}')
                else:
                    await media.edit_titlesort(titlevalue,lock=1)
                    log.info(f'{media.title}: 改变标题排序为 {titlevalue}')

    async def _plexscan(self,section):
        log.info(f"{section.title}：开始扫描媒体库")
        await section.refresh()

    async def _synctask(self,media):
        async with self.sem:
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
            except asyncio.CancelledError:
                pass
            except:
                log.error(f'{media.title}\{emby_media.Name} ：\n {traceback.format_exc()}')

    async def _plex_sync_emby(self,media,tasks):
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
        tasks.remove(asyncio.current_task())

    async def _emby_sync_plex(self,media,tasks):
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
        tasks.remove(asyncio.current_task())

    async def _merge(self,ids,name):
        async with self.sem:
            log.info(f'{name}: 开始合并')
            await self.emby.merge_version(ids)
            log.info(f'{name}: 合并完成，合并IDs:{ids}')

    async def _emby_movie_merge(self,lb):
        mediaid = []
        #若为混合内容，则只获取电影类型媒体
        if isinstance(lb,embyserver.MixContent):
            medias = await lb.get_movie()
        else:
            medias = await lb.all()
        index = 0
        for media in medias:
            #判断是否有刮削
            if media.ProviderIds:
                if media.tmdbid:
                    mediaid.append({media.tmdbid:index})
                else:
                    log.warning(f'{media.Name}：没有tmdbid信息')
            else:
                log.warning(f'{media.Name}：没有ProviderIds信息，请检查刮削情况')
            index += 1
        log.info(f"{lb.Name}：开始合并版本")
        match_dict = {}
        task = []
        #将重复媒体的index存入列表,形成字典
        for id_dict in mediaid:
            for id,i in id_dict.items():
                if match_dict.get(id):
                    origin_list = match_dict.get(id)
                    origin_list.append(i)
                    match_dict.update({id:origin_list})
                else:
                    match_dict.update({id:[i]})
        #遍历字典，开始合并
        for v in match_dict.values():
            #找出重复元素
            if len(v) > 1:
                ids = [medias[i].Id for i in v]
                task.append(self._merge(ids,medias[v[0]].Name))
        await asyncio.gather(*task)
        task.clear()
        log.info(f"{lb.Name}：合并完成")

    async def _emby_sort(self,media):
        async with self.sem:
            convert = pinyin(media.formatchs(media.Name).strip("-"),style=Style(4),heteronym=False)
            titlevalue = str.join('',list(map(lambda x:x[0],convert)))
            split_title = titlevalue.split('-')
            final = ''
            for t in split_title:
                if t != '':
                    final += ","+t
            final = final.strip(",")
            #在标题搜索的最后加入整个name的拼音
            if len(split_title) != 1:
                final += ","+"".join(split_title)
            if media.SortName != (titlevalue[0] if titlevalue[0].isdigit() else titlevalue) or \
            media.OriginalTitle != final:
                await media.fetchitem()
                media.data["OriginalTitle"] = final
                media.data["ForcedSortName"] = titlevalue[0] if titlevalue[0].isdigit() else titlevalue
                media.data["SortName"] = titlevalue[0] if titlevalue[0].isdigit() else titlevalue
                media.data["LockedFields"].append("OriginalTitle") if  media.data["LockedFields"].count("OriginalTitle") == 0 else None
                media.data["LockedFields"].append("SortName") if  media.data["LockedFields"].count("SortName") == 0 else None
                log.info(f'{media.Name}: 改变标题排序为 {titlevalue}')
                await media.edit(media.data)
            else:
                log.info(f'{media.Name}: 已经存在标题排序{titlevalue}')

    async def _emby_role(self):
        person = await self.emby.get_person()
        for p in person:
            if p.check_chs(p.Name):
                log.info(f'{p.Name}：已有中文信息')
                continue
            if p.ProviderIds:
                if p.tmdbid:
                    data = await self.emby.request_tmdb(self.session,p.tmdbid)
                    if data['chs']:
                        await p.fetchitem()
                        p.data["Name"] = data['chs']
                        await p.edit(p.data)
                        log.info(f'{p.Name}：修改为data["chs"]')
                    else:
                        log.info(f'{p.Name}：tmdb没有中文信息')
                else:
                    log.warning(f'{p.Name}：没有Tmdbid信息')
            else:
                log.warning(f'{p.Name}：没有ProviderIds信息')

    async def _embyscan(self,section):
        log.info(f"{section.Name}：开始扫描媒体库")
        await section.refresh()

    async def _emby_season_title(self,media):
        if not media.tmdbid:
            log.warning(f"Emby: {media.Name} 没有tmdbid，无法搜索季标题，跳过")
            return
        for se in await media.seasons():
            title = await media.season_title(media._server.session,
                                    media.tmdbid,se.IndexNumber)
            if title:
                await se.fetchitem()
                se.data["Name"] = title
                log.info(f'Emby: {media.Name}: 改变季{se.IndexNumber}标题为 {title}')
                await se.edit(se.data)
            else:
                log.info(f'Emby: {media.Name}: 季{se.IndexNumber}没有找到相关数据')

    async def plex_basetask(self,method):
        tasks = []
        #medias = []
        library = await self.plex.library()
        sections = library.sections()
        for section in sections:
            data = await section.all()
            for media in data:
                #await media.fetchitem()
                tasks.append(method(media))
                #task = asyncio.create_task(method(media=media))
                #tasks.append(task)
        
        #for task in asyncio.as_completed(tasks):
        #   await task
        await asyncio.gather(*tasks)
        tasks.clear()

    async def emby_basetask(self,method):
        tasks = []
        emby_library = await self.emby.library()
        for lb in emby_library:
            if lb.CollectionType in (None,"movies","tvshows"):
                data = await lb.all()
                for media in data:
                    tasks.append(method(media=media))
            else:
                log.warning(f'{lb.Name}：只支持电影、剧集和混合内容库，跳过此库')
                continue

        await asyncio.gather(*tasks)
        tasks.clear()

    async def plex_sort(self):
        log.info("Plex：开始进行标题排序，拼音搜索...")
        try:
            await self.plex_basetask(self._plexsort)
            log.info("Plex：标题排序，拼音搜索执行完毕")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def plex_role(self):
        log.info("Plex：开始进行演员中文化...")
        try:
            await self.plex_basetask(self._plexrole)
            log.info("Plex：演员中文化执行完毕")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def plex_scan(self,scheduler):
        log.info("Plex：开始初始化定时刷新媒体库任务...")
        try:
            library = await self.plex.library()
            sections = library.sections()
            for lb in PLEX_SACN_TASK:
                for name,crontab in lb.items():
                    exist = False
                    for s in sections:
                        if s.title == name:
                            scheduler.add_job(self._plexscan,args=[s], trigger=CronTrigger.from_crontab(crontab))
                            exist = True
                    if not exist:
                        log.info(f"{name}：未在plex库中找到{name}库，无法启动此名称刷新媒体库任务，请检查配置文件")
            log.info("Plex：定时刷新媒体库任务已启动")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def emby_scan(self,scheduler):
        log.info("Emby：开始初始化定时刷新媒体库任务...")
        try:
            library = await self.emby.library()
            for lb in EMBY_SACN_TASK:
                for name,crontab in lb.items():
                    exist = False
                    for lb in library:
                        if lb.Name == name:
                            scheduler.add_job(self._embyscan,args=[lb], trigger=CronTrigger.from_crontab(crontab))
                            exist = True
                    if not exist:
                        log.info(f"{name}：未在Emby库中找到{name}库，无法启动此名称刷新媒体库任务，请检查配置文件")
            log.info("Emby：定时刷新媒体库任务已启动")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def synctask(self):
        log.info("开始同步plex，emby全部观看历史")
        try:
            await self.plex_basetask(self._synctask)
            log.info("同步plex，emby全部观看历史完毕")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def emby_movie_merge(self):
        tasks = []
        log.info("Emby：开始合并版本任务，初始化中...")
        try:
            emby_library = await self.emby.library()
            # 在emby媒体库中找出混合内容库和电影库
            for lb in emby_library:
                if lb.CollectionType in (None,"movies"):
                    tasks.append(self._emby_movie_merge(lb))
                else:
                    log.info(f"{lb.Name}：非电影库或者混合内容，Emby合并版本任务跳过此库")
            await asyncio.gather(*tasks)
            tasks.clear()
            log.info("Emby：合并版本任务完毕")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def emby_role(self):
        log.info("Emby：开始进行演员中文化...")
        try:
            await self._emby_role()
            log.info("Emby：演员中文化执行完毕")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def emby_sort(self):
        log.info("Emby：开始进行标题排序，拼音搜索任务...")
        try:
            await self.emby_basetask(self._emby_sort)
            log.info("Emby：标题排序，拼音搜索任务执行完毕")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def emby_season_title(self):
        log.info("Emby：开始进行修正季标题任务...")
        try:
            tasks = []
            emby_library = await self.emby.library()
            for lb in emby_library:
                if isinstance(lb,embyserver.MixContent):
                    data = await lb.get_series()
                    for media in data:
                        tasks.append(self._emby_season_title(media=media))
                elif isinstance(lb,embyserver.SeriesLibrary):
                    data = await lb.all()
                    for media in data:
                        tasks.append(self._emby_season_title(media=media))
                else:
                    log.warning(f'{lb.Name}：修正季标题只支持剧集和混合内容库，跳过此库')
                    continue
            await asyncio.gather(*tasks)
            tasks.clear()
            log.info("Emby：修正季标题任务任务执行完毕")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())

    async def cronsync(self):
        try:
            log.info('开始同步进度')
            tasks = []
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
                    task = asyncio.create_task(self._plex_sync_emby(media=_cont,tasks=tasks))
                    tasks.append(task)
                else:
                    break
            #所有新增plex已观看
            for _his in plex_history:
                if not _his.viewedAt:
                    _his.viewedAt = _his.lastViewedAt
                if _his.viewedAt - self.last_viewed > 0:
                    task = asyncio.create_task(self._plex_sync_emby(media=_his,tasks=tasks))
                    tasks.append(task)
                else:
                    break
            #所有新增emby已观看
            for _his in emby_history:
                if _his.LastPlayedDate > self.last_vieweddate:
                    task = asyncio.create_task(self._emby_sync_plex(media=_his,tasks=tasks))
                    tasks.append(task)
                else:
                    break
            #所有新增emby继续观看
            for _cont in emby_cont:
                if _cont.LastPlayedDate > self.last_viewingdate:
                    task = asyncio.create_task(self._emby_sync_plex(media=_cont,tasks=tasks))
                    tasks.append(task)
                else:
                    break
            
            for task in asyncio.as_completed(tasks):
                await task
            log.info("同步进度完毕，等待下一次运行")
        except asyncio.CancelledError:
            pass
        except:
            log.critical(traceback.format_exc())
            
    async def close(self):
        if hasattr(self,"session"):
            await self.session.close()