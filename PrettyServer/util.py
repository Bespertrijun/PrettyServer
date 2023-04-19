import asyncio
import opencc
from exception import FailRequest
from log import log
from aiohttp import ContentTypeError
from aiohttp import ClientSession
from conf import TMDB_API

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

    def issimple(name):
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

    def formatchs(self,name):
        chs = ''
        for n,ch in enumerate(name):
            if '\u4e00' <= ch <= '\u9fff':
                chs += ch
            elif ch.isalnum():
                chs += f'{ch}-'
            elif ch == '-':
                pass
            elif n == 0:
                pass
            else:
                chs += '-'
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
            path_url = f'/Users/{self._server.userid}/Items/{ekey}'
        data = await self._server.query(path_url,msg='请求失败，请检查网络或ekey')
        return data

    async def query(self, path, method=None, headers=None, msg:str=None):
        url = self.url + path
        header = self.header
        if not hasattr(self,'session'):
            self.session = ClientSession()
        if headers:         
            header.update(headers)
        if method is not None:
            if method.upper() == 'POST':
                async with self.session.post(url,headers=header) as res:
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
        if self._server.type == 'plex':
            path = f'/:/timeline?ratingKey={self.ratingKey}&key={self.key}&identifier=com.plexapp.plugins.library&time={time}&state=stopped&duration={self.duration}'
            await self._server.query(path,msg='请求错误，调整观看进度失败')
        elif self._server.type == 'emby':
            payload = {
                'ItemId':self.Id,
                'PositionTicks': time
                }
            path = f'/Sessions/Playing/Stopped'
            url = self.bulidurl(path,payload)
            await self._server.query(url,method='post',msg='请求错误，调整观看进度失败')
    
    async def request_tmdb(self,session,cid):
        url = f'https://api.themoviedb.org/3/person/{cid}?api_key={TMDB_API}&language=zh-CN'
        while True:
            try:
                async with session.get(url) as res:
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
                            break
                        else:
                            data[respond['name']]['chs'] = None
                            break
                    else: 
                        return {'chs':[]}
            except:
                log.error('连接失败，正在重试...')
                await asyncio.sleep(1)
        return data[respond['name']]['chs']