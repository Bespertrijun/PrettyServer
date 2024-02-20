import opencc
import time as Time
from util.exception import FailRequest
from aiohttp import ContentTypeError
from aiohttp import ClientSession
from util.exception import FailRequest
from conf.conf import TMDB_API,PROXY,ISPROXY

class Util():
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
    
    def convertTime(self,time):
        if self._server.type == 'plex':
            return time*10000
        elif self._server.type == 'emby':
            return int(time/10000)

    def pretty_ep_out(self):
        if self._server.type == 'plex':
            return f'S{str(self.parentIndex).zfill(2)}E{str(self.index).zfill(2)}'
        elif self._server.type == 'emby':
            return f'S{str(self.ParentIndexNumber).zfill(2)}E{str(self.IndexNumber).zfill(2)}'

    async def _fetchitem(self,ekey):
        """
            ekey : ratingKey
        """
        if self._server.type == 'plex':
            path_url = f'/library/metadata/{ekey}'
        elif self._server.type == 'emby':
            if self._server.userid:
                path_url = f'/Users/{self._server.userid}/Items/{ekey}'
            else:
                path_url = f'/Items/{ekey}'
        data = await self._server.query(path_url,msg='请求失败，请检查网络或ekey')
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
                async with self.session.post(url,headers=header,data=data,json=json) as res:
                    if res.status in (200, 201, 204):
                        try:
                            data = await res.json()
                        except ContentTypeError:
                            data = res
                    else:
                        raise FailRequest(msg)
                #headers.update({'Content-type': 'application/x-www-form-urlencoded'})
            elif method.upper() == 'PUT':
                async with self.session.put(url,headers=header) as res:
                    if res.status in (200, 201, 204):
                        try:
                            data = await res.json()
                        except ContentTypeError:
                            data = res
                    else:
                        raise FailRequest(msg)
            elif method.upper() == 'DELETE':
                async with self.session.delete(url,headers=header) as res:
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
            async with self.session.get(url,headers=header) as res:
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
        elif self._server.type == 'emby':
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
    
    async def season_title(self,series_id,season_number):
        path = f"https://api.tmdb.org/3/tv/{series_id}/season/{season_number}/translations?api_key={TMDB_API}"
        proxy = PROXY if ISPROXY else None
        async with self._server.tmdb_session.get(path,proxy=proxy) as res:
            if res.status == 200:
                respond =  await res.json()
                for trans in respond.get("translations"):
                    if trans.get("iso_3166_1") == "CN":
                        if trans["data"].get("name"):
                            return trans["data"].get("name")
                        else:
                            return None
            if res.status == 404:
                raise FailRequest("TMDBID或者季数 不存在")
            else:
                raise FailRequest("获取季标题失败")

    async def get_role_from_id(self,type,tmdbid):
        """
            type: movie for movie, tv for tv
        """
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
                return tmdb_data
            if res.status == 404:
                raise FailRequest("TMDBID 不存在")
            else:
                raise FailRequest("获取演员列表失败")