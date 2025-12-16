import opencc
import time as Time
from util.exception import FailRequest
from aiohttp import ContentTypeError
from aiohttp import ClientSession,ClientTimeout
from util.exception import FailRequest
from conf.conf import TMDB_API,PROXY,ISPROXY
import asyncio

_timeout = ClientTimeout(
    connect=3,          # 3秒内必须建立起连接
    sock_connect=5,     # 5秒内必须完成socket连接
    sock_read=10,       # 等待服务器发送数据的间隔最多10秒
    total=30            # 整个请求（包括上传数据）必须在30秒内完成
)

class Util():
    # 类级别的缓存字典
    _role_cache = {}  # 缓存已获取的演员数据
    _pending_requests = {}  # 正在进行的请求（避免重复请求）
    def bulidurl(self,url,payload:dict=None):
        if '?' in url and payload:
            for k,v in payload.items():
                url += f'&{k}={v}'
        elif payload:
            url += '?'
            for n,k in enumerate(payload):
                if n == 0:
                    url += f'{k}={payload[k]}'
                else:
                    url += f'&{k}={payload[k]}'
        return url

    def issimple(self,name):
        converter = opencc.OpenCC('t2s.json')
        if converter.convert(name) == name:
            return True
        else:
            return False

    def check_chs(self,name):
        for ch in name:
            if '\u4e00' <= ch <= '\u9fff' or ch == ' ' or ch == '·':
                continue
            else:
                return False
        return True

    def has_chinese_no_japanese(self, str):
        """
        判断字符串是否包含中文且不包含日文

        Args:
            str: 待检测的字符串

        Returns:
            bool: 包含中文且不含日文假名返回 True，否则返回 False

        说明:
            - 中文字符范围: CJK 统一汉字 U+4E00-U+9FFF
            - 日文平假名范围: U+3040-U+309F
            - 日文片假名范围: U+30A0-U+30FF
            - 半角片假名范围: U+FF65-U+FF9F
            - 严格模式: 只要包含任何日文假名就返回 False
        """
        has_chinese = False

        for ch in str:
            # 检测日文假名（平假名、片假名、半角片假名）
            if ('\u3040' <= ch <= '\u309f' or  # 平假名
                '\u30a0' <= ch <= '\u30ff' or  # 片假名
                '\uff65' <= ch <= '\uff9f'):   # 半角片假名
                return False

            # 检测中文字符
            if '\u4e00' <= ch <= '\u9fff':
                has_chinese = True

        return has_chinese

    def checkchs(self,name):
        chs_list = []
        chs = ''
        lenth = len(name)
        for n,ch in enumerate(name):
            if n+1 != lenth:
                if '\u4e00' <= ch <= '\u9fff':
                    chs+=ch
                    if not ('\u4e00' <= name[n+1] <= '\u9fff'):
                        chs_list.append(chs)
                        chs = ''
                else:
                    pass
            else:
                if '\u4e00' <= ch <= '\u9fff' and chs != '':
                    chs+=ch
                    chs_list.append(chs)
        if len(chs_list) == 1:
            if len(name) == len(chs_list[0]):
                return []
        return chs_list

    def formatchs(self,name):
        chs = ''
        for ch in name:
            if '\u4e00' <= ch <= '\u9fff':
                chs += ch
            elif ch.isalnum():
                chs += ch    
            elif ch == '-':
                pass
            else:
                chs += '-'
        chs_list = self.checkchs(name)
        if chs_list:
            for ch in chs_list:
                chs+= '-' + ch
        return chs

    def covertType(self,type):
        if type.lower() == 'movies':
            return 'movie'
        elif type.lower() == 'tvshows':
            return 'series'
    
    def convertTime(self,time,sync_type):
        if time == None:
            time = 0
        if sync_type in (0,2):
            return time
        else:
            if self._server.type == 'plex':
                return time*10000
            elif self._server.type in ('emby','jellyfin'):
                return int(time/10000)

    def pretty_ep_out(self):
        if self._server.type == 'plex':
            return f'S{str(self.parentIndex).zfill(2)}E{str(self.index).zfill(2)}'
        elif self._server.type in ('emby','jellyfin'):
            return f'S{str(self.ParentIndexNumber).zfill(2)}E{str(self.IndexNumber).zfill(2)}'

    async def _fetchitem(self,ekey):
        """
            ekey : ratingKey
        """
        if self._server.type == 'plex':
            path_url = f'/library/metadata/{ekey}'
        elif self._server.type in ('emby','jellyfin'):
            if self._server.userid:
                path_url = f'/Users/{self._server.userid}/Items/{ekey}'
            else:
                payload = {
                    'Ids':ekey,
                    "Fields":"OriginalTitle,Etag,DateCreated,CanDelete,CanDownload,PresentationUniqueKey,SupportsSync,SortName,ForcedSortName,PremiereDate,ExternalUrls,Path,Overview,Taglines,Genres,FileName,ProductionYear,RemoteTrailers,ProviderIds,ParentId,People,Studios,GenreItems,TagItems,LocalTrailerCount,ChildCount,DisplayPreferencesId,Status,PrimaryImageAspectRatio,DisplayOrder,LockedFields,LockData"
                }
                path_url = self.bulidurl("/Items",payload)
        data = await self._server.query(path_url,msg='请求失败，请检查网络或ekey')
        if not self._server.userid:
            data = data['Items'][0 ]
        return data

    async def query(self, path, method=None, headers=None, data=None, json=None,msg:str=None):
        url = self.url + path
        if hasattr(self,"type"):
            if self.type == "drive":
                url = path
        header = self.header
        if not hasattr(self,'session'):
            self.session = ClientSession()
        if headers:         
            header.update(headers)
        if method is not None:
            if method.upper() == 'POST':
                async with self.session.post(url,headers=header,data=data,json=json,timeout=_timeout) as res:
                    if res.status in (200, 201, 204):
                        try:
                            data = await res.json()
                        except ContentTypeError:
                            data = res
                    else:
                        raise FailRequest(msg)
                #headers.update({'Content-type': 'application/x-www-form-urlencoded'})
            elif method.upper() == 'PUT':
                async with self.session.put(url,headers=header,timeout=_timeout) as res:
                    if res.status in (200, 201, 204):
                        try:
                            data = await res.json()
                        except ContentTypeError:
                            data = res
                    else:
                        raise FailRequest(msg)
            elif method.upper() == 'DELETE':
                async with self.session.delete(url,headers=header,timeout=_timeout) as res:
                    if res.status in (200, 201, 204):
                        try:
                            data = await res.json()
                        except ContentTypeError:
                            data = res
                    else:
                        raise FailRequest(msg)
            else:
                #print("Invalid request method provided: {method}".format(method=method))
                return
        else:
            async with self.session.get(url,headers=header,timeout=_timeout) as res:
                if res.status in (200, 201, 204):
                    try:
                        data = await res.json()
                    except ContentTypeError:
                        data = res
                        if hasattr(self,"type"):
                            if self.type == "drive":
                                try:
                                    data = await res.text()
                                except UnicodeDecodeError:
                                    data = await res.read()
                else:
                    raise FailRequest(msg)
        #log.debug('%s %s', method.__name__.upper(), url)
        return data
    
    async def watched(self):
        if self._server.type == 'plex':
            path = f'/:/scrobble?identifier=com.plexapp.plugins.library&key={self.ratingKey}'
            await self._server.query(path,msg='请求错误，调整已观看失败')
        elif self._server.type == 'emby':
            path = f'/Users/{self._server.userid}/PlayedItems/{self.Id}'
            await self._server.query(path,method='post',msg='请求错误，调整已观看失败')

    async def unwatched(self):
        if self._server.type == 'plex':
            path = f'/:/unscrobble?identifier=com.plexapp.plugins.library&key={self.ratingKey}'
            await self._server.query(path,msg='请求错误，调整未观看失败')
        elif self._server.type == 'emby':
            path = f'/Users/{self._server.userid}/PlayedItems/{self.Id}/Delete'
            await self._server.query(path,method='post',msg='请求错误，调整未观看失败')

    async def timeline(self,time):
        now_str = str(Time.time()).replace('.','')
        if self._server.type == 'plex':
            path = f'/:/timeline?ratingKey={self.ratingKey}&key={self.key}&identifier=com.plexapp.plugins.library&time={time}&state=stopped&duration={self.duration}'
            await self._server.query(path,msg='请求错误，调整观看进度失败')
        elif self._server.type in ('emby','jellyfin'):
            path = f'/Sessions/Playing'
            payload = {
                "PositionTicks": time,
                "PlaybackStartTimeTicks": now_str,
                "ItemId": self.Id,
                "PlaySessionId": "77d5a0f04e5b4d2fb25773486d292f3f",
            }
            await self._server.query(path,method='post',json=payload,msg='请求错误，调整观看开始时间失败')
            payload = {
                'ItemId':self.Id,
                'PositionTicks': time,
                'PlaybackStartTimeTicks':now_str,
                "PlaySessionId": "77d5a0f04e5b4d2fb25773486d292f3f"
                }
            path = f'/Sessions/Playing/Stopped'
            await self._server.query(path,method='post',json=payload,msg='请求错误，调整观看进度失败')

    async def get_chs_name(self,cid):
        url = f'https://api.tmdb.org/3/person/{cid}?api_key={TMDB_API}&language=zh-CN'
        proxy = PROXY if ISPROXY else None
        async with self._server.tmdb_session.get(url,proxy=proxy) as res:
            if res.status == 200:
                respond =  await res.json()
                data = {}
                data[respond['name']] = {}
                data[respond['name']]['id'] = respond['id']
                data[respond['name']]['also_known_as'] = respond['also_known_as']
                if respond['also_known_as']:
                    for chs_name in respond['also_known_as']:
                        if self.check_chs(chs_name):
                            if self.issimple(chs_name):
                                data[respond['name']]['chs'] = chs_name
                                break
                            else:
                                data[respond['name']]['chs'] = None
                        else:
                            data[respond['name']]['chs'] = None
                else:
                    data[respond['name']]['chs'] = None
            elif res.status == 404:
                raise FailRequest("演员CID 不存在")
            else: 
                raise FailRequest("获取演员中文名失败")
        return {'chs':data[respond['name']]['chs']}
    
    async def season_title(self, series_id, season_number):
        """
        获取季的中文标题（优先 CN，回退到 SG）

        Args:
            series_id: 剧集的 TMDB ID
            season_number: 季号

        Returns:
            str | None: 返回中文标题，如果没有则返回 None
        """
        respond = await self._fetch_season_translations(series_id, season_number)

        cn_title = None
        sg_title = None

        for trans in respond.get("translations", []):
            iso = trans.get("iso_3166_1")
            name = trans.get("data", {}).get("name")

            if iso == "CN" and name:
                cn_title = name
            elif iso == "SG" and name:
                sg_title = name

        # 优先返回 CN，没有则返回 SG
        return cn_title if cn_title else sg_title

    async def movie_title(self, tmdbid):
        """
        获取电影的中文标题（不含日文）

        优先级顺序：
        1. CN alternative_titles
        2. CN translations
        3. SG alternative_titles
        4. SG translations

        Args:
            tmdbid: 电影的 TMDB ID

        Returns:
            str | None: 返回不含日文的中文标题，如果没有则返回 None
        """
        # 获取两个数据源
        alt_data = None
        trans_data = None

        try:
            alt_data = await self._fetch_movie_alternative_titles(tmdbid)
        except Exception:
            pass

        try:
            trans_data = await self._fetch_movie_translations(tmdbid)
        except Exception:
            pass

        # 优先级 1: CN alternative_titles
        if alt_data:
            for alt in alt_data.get("titles", []):
                if alt.get("iso_3166_1") == "CN":
                    title = alt.get("title")
                    if title and self.has_chinese_no_japanese(title):
                        return title

        # 优先级 2: CN translations
        if trans_data:
            for trans in trans_data.get("translations", []):
                if trans.get("iso_3166_1") == "CN":
                    title = trans.get("data", {}).get("title")
                    if title and self.has_chinese_no_japanese(title):
                        return title

        # 优先级 3: SG alternative_titles
        if alt_data:
            for alt in alt_data.get("titles", []):
                if alt.get("iso_3166_1") == "SG":
                    title = alt.get("title")
                    if title and self.has_chinese_no_japanese(title):
                        return title

        # 优先级 4: SG translations
        if trans_data:
            for trans in trans_data.get("translations", []):
                if trans.get("iso_3166_1") == "SG":
                    title = trans.get("data", {}).get("title")
                    if title and self.has_chinese_no_japanese(title):
                        return title

        # 都没找到，返回 None
        return None

    async def show_title(self, tmdbid):
        """
        获取剧集的中文标题（不含日文）

        优先级顺序：
        1. CN alternative_titles
        2. CN translations
        3. SG alternative_titles
        4. SG translations

        Args:
            tmdbid: 剧集的 TMDB ID

        Returns:
            str | None: 返回不含日文的中文标题，如果没有则返回 None
        """
        # 获取两个数据源
        alt_data = None
        trans_data = None

        try:
            alt_data = await self._fetch_tv_alternative_titles(tmdbid)
        except Exception:
            pass

        try:
            trans_data = await self._fetch_tv_translations(tmdbid)
        except Exception:
            pass

        # 优先级 1: CN alternative_titles
        if alt_data:
            for alt in alt_data.get("results", []):
                if alt.get("iso_3166_1") == "CN":
                    title = alt.get("title")
                    if title and self.has_chinese_no_japanese(title):
                        return title

        # 优先级 2: CN translations
        if trans_data:
            for trans in trans_data.get("translations", []):
                if trans.get("iso_3166_1") == "CN":
                    title = trans.get("data", {}).get("name")
                    if title and self.has_chinese_no_japanese(title):
                        return title

        # 优先级 3: SG alternative_titles
        if alt_data:
            for alt in alt_data.get("results", []):
                if alt.get("iso_3166_1") == "SG":
                    title = alt.get("title")
                    if title and self.has_chinese_no_japanese(title):
                        return title

        # 优先级 4: SG translations
        if trans_data:
            for trans in trans_data.get("translations", []):
                if trans.get("iso_3166_1") == "SG":
                    title = trans.get("data", {}).get("name")
                    if title and self.has_chinese_no_japanese(title):
                        return title

        # 都没找到，返回 None
        return None

    async def get_role_from_id(self,type,tmdbid):
        """
            type: movie for movie, tv for tv
            优化版本：添加缓存和请求去重，减少内存占用
        """
        cache_key = f"{type}:{tmdbid}"

        # 1. 检查缓存
        if cache_key in Util._role_cache:
            return Util._role_cache[cache_key]

        # 2. 检查是否有正在进行的相同请求，避免重复请求
        if cache_key in Util._pending_requests:
            return await Util._pending_requests[cache_key]

        # 3. 创建新请求任务
        async def fetch():
            if type == "tv":
                url = f'https://api.tmdb.org/3/tv/{tmdbid}/aggregate_credits?api_key={TMDB_API}&language=zh-CN'
            elif type == "movie":
                url = f'https://api.tmdb.org/3/movie/{tmdbid}/credits?api_key={TMDB_API}&language=zh-CN'
            else:
                raise FailRequest("Type 参数错误，只支持tv，movie")

            proxy = PROXY if ISPROXY else None
            async with self._server.tmdb_session.get(url,proxy=proxy) as res:
                if res.status == 200:
                    tmdb_data = await res.json()
                    # 缓存结果
                    Util._role_cache[cache_key] = tmdb_data
                    return tmdb_data
                if res.status == 404:
                    raise FailRequest("TMDBID 不存在")
                else:
                    raise FailRequest("获取演员列表失败")

        # 记录正在进行的请求
        task = asyncio.create_task(fetch())
        Util._pending_requests[cache_key] = task

        try:
            result = await task
            return result
        finally:
            # 请求完成后移除
            Util._pending_requests.pop(cache_key, None)

    @classmethod
    def clear_role_cache(cls):
        """清空演员数据缓存，释放内存"""
        cls._role_cache.clear()
        cls._pending_requests.clear()

    async def _fetch_movie_translations(self, tmdbid):
        """
        获取电影的翻译数据

        Args:
            tmdbid: 电影的 TMDB ID

        Returns:
            dict: TMDB API 返回的原始 JSON 数据

        Raises:
            FailRequest: API 请求失败时抛出
        """
        path = f"https://api.themoviedb.org/3/movie/{tmdbid}/translations?api_key={TMDB_API}"
        proxy = PROXY if ISPROXY else None
        async with self._server.tmdb_session.get(path, proxy=proxy) as res:
            if res.status == 200:
                return await res.json()
            elif res.status == 404:
                raise FailRequest("电影TMDBID不存在")
            else:
                raise FailRequest("获取电影翻译数据失败")

    async def _fetch_tv_translations(self, tmdbid):
        """
        获取剧集的翻译数据

        Args:
            tmdbid: 剧集的 TMDB ID

        Returns:
            dict: TMDB API 返回的原始 JSON 数据

        Raises:
            FailRequest: API 请求失败时抛出
        """
        path = f"https://api.themoviedb.org/3/tv/{tmdbid}/translations?api_key={TMDB_API}"
        proxy = PROXY if ISPROXY else None
        async with self._server.tmdb_session.get(path, proxy=proxy) as res:
            if res.status == 200:
                return await res.json()
            elif res.status == 404:
                raise FailRequest("剧集TMDBID不存在")
            else:
                raise FailRequest("获取剧集翻译数据失败")

    async def _fetch_season_translations(self, series_id, season_number):
        """
        获取季的翻译数据

        Args:
            series_id: 剧集的 TMDB ID
            season_number: 季号

        Returns:
            dict: TMDB API 返回的原始 JSON 数据

        Raises:
            FailRequest: API 请求失败时抛出
        """
        path = f"https://api.themoviedb.org/3/tv/{series_id}/season/{season_number}/translations?api_key={TMDB_API}"
        proxy = PROXY if ISPROXY else None
        async with self._server.tmdb_session.get(path, proxy=proxy) as res:
            if res.status == 200:
                return await res.json()
            elif res.status == 404:
                raise FailRequest("TMDBID或季数不存在")
            else:
                raise FailRequest("获取季翻译数据失败")

    async def _fetch_movie_alternative_titles(self, tmdbid):
        """
        获取电影的别名

        Args:
            tmdbid: 电影的 TMDB ID

        Returns:
            dict: TMDB API 返回的原始 JSON 数据

        Raises:
            FailRequest: API 请求失败时抛出
        """
        path = f"https://api.themoviedb.org/3/movie/{tmdbid}/alternative_titles?api_key={TMDB_API}"
        proxy = PROXY if ISPROXY else None
        async with self._server.tmdb_session.get(path, proxy=proxy) as res:
            if res.status == 200:
                return await res.json()
            elif res.status == 404:
                raise FailRequest("电影TMDBID不存在")
            else:
                raise FailRequest("获取电影别名失败")

    async def _fetch_tv_alternative_titles(self, series_id):
        """
        获取剧集的别名数据

        Args:
            series_id: 剧集的 TMDB ID

        Returns:
            dict: TMDB API 返回的原始 JSON 数据

        Raises:
            FailRequest: API 请求失败时抛出
        """
        path = f"https://api.themoviedb.org/3/tv/{series_id}/alternative_titles?api_key={TMDB_API}"
        proxy = PROXY if ISPROXY else None
        async with self._server.tmdb_session.get(path, proxy=proxy) as res:
            if res.status == 200:
                return await res.json()
            elif res.status == 404:
                raise FailRequest("剧集TMDBID不存在")
            else:
                raise FailRequest("获取剧集别名失败")