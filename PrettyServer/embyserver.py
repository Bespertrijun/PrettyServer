import aiohttp
from attr import has
from util import Util
from log import log
from datetime import datetime
from exception import MediaTypeError,AsyncError,InvalidParams

class Embyserver(Util):
    def __init__(self,emby_url,emby_token=None,username=None,password=None) -> None:
        if username and password:
            self.uname = username
            self.pw = password
        else:
            self.token = emby_token
            self.header = {'X-Emby-Token': emby_token,"accept": "application/json"}
        self.url = emby_url.rstrip('/')
        self.type = 'emby'
        self._server = self

    async def login(self):
        if not hasattr(self,'session'):
            self.session = aiohttp.ClientSession()
        header = {'x-emby-authorization':
            'Emby UserId="python",'
            'Client="python",'
            'Device="Embypretty",'
            'DeviceId="Emby sucks",'
            'Version="1.0.1"'}
        payload = {
            'Username':self.uname,
            'Pw':self.pw
        }
        self.header = header
        url = self.bulidurl(f'/Users/AuthenticateByName',payload)
        data = await self.query(url,method='POST',headers=self.header,
                                msg='请求失败，请检查账密')
        self.token = data.get('AccessToken')
        self.userid = data['User'].get('Id')
        self.header = {'X-Emby-Token': self.token,"accept": "application/json"}

    async def library(self):
        path = f'/Users/{self.userid}/Views'
        data = await self.query(path,msg='请求错误')
        librarys = []
        for lb in data['Items']:
            librarys.append(Library(lb,self._server))
        return librarys

    async def close(self):
        await self.session.close()

    async def guidsearch(self,guid):
        if not hasattr(self,'userid'):
            await self.login()
        path = f'/Items'
        payload = {
            'UserId':self.userid,
            'Recursive': True,
            'AnyProviderIdEquals':f"{guid.replace('://', '.')}"
        }
        url = self.bulidurl(path,payload)
        data = await self.query(url,msg='请求失败，搜索未完成')
        emby_medias = []
        if data.get('Items'):
            for item in data.get('Items'):
                if item.get('Type').lower() == 'movie':
                    emby_medias.append(Movie(item,self._server))
                elif item.get('Type').lower() == 'series':
                    emby_medias.append(Show(item,self._server))
        return emby_medias

    async def hub_continue(self):
        if not hasattr(self,'userid'):
            await self.login()
        payload = {
            'Recursive':True
        }
        path = self.bulidurl(f'/Users/{self.userid}/Items/Resume',payload)
        data = await self._server.query(path)
        medias = []
        for item in data.get('Items'):
            if item['UserData'].get("LastPlayedDate"):
                if item.get('Type').lower() == 'movie':
                    media = Movie(item,self._server)
                elif item.get('Type').lower() == 'episode':
                    media = Episode(item,self._server)
                media.LastPlayedDate = datetime.fromisoformat(
                    item['UserData'].get("LastPlayedDate")[:-1])
                medias.append(media)
        return medias

    async def history(self,**kwargs):
        if not hasattr(self,'userid'):
            await self.login()
        if kwargs:
            payload = kwargs
        else:
            payload = {
                'IsPlayed': True,
                'SortBy':'DatePlayed',
                'SortOrder':'Descending',
                'Recursive':True,
                'Limit':20
            }
        path = self.bulidurl(f'/Users/{self.userid}/Items',payload)
        data = await self._server.query(path,msg='请求历史失败')
        medias = []
        if data.get('TotalRecordCount') == 0:
            log.warning('Emby无历史播放记录')
        else:
            for item in data.get('Items'):
                if item.get('Type').lower() == 'movie':
                    media = Movie(item,self._server)
                elif item.get('Type').lower() == 'episode':
                    media = Episode(item,self._server)
                media.LastPlayedDate = datetime.fromisoformat(
                    item['UserData'].get("LastPlayedDate")[:-1])
                medias.append(media)
        return medias

class Library(Util):
    def __init__(self,data,server) -> None:
        self.data = data
        self._server = server
        self._loaddata()

    def _loaddata(self):
        self.Name = self.data.get('Name')
        self.ServerId = self.data.get('ServerId')
        self.Id = self.data.get('Id')
        self.Etag = self.data.get('Etag')
        self.PresentationUniqueKey = self.data.get('PresentationUniqueKey')
        self.SortName = self.data.get('SortName')
        self.CollectionType = self.data.get('CollectionType')

    async def fetchitems(self,**kwargs):
        path = f'/Users/{self._server.userid}/Items'
        payload = kwargs
        url = self.bulidurl(path,payload)
        data = await self._server.query(url)
        return data
    
    async def all(self):
        data = await self.fetchitems(Recursive=True,ParentId=self.Id,
                                     Limit=10,
                                     IncludeItemTypes=self.covertType(self.CollectionType))
        if self.CollectionType.lower() == 'movies':
            movies = []
            for item in data.get('Items'):
                movies.append(Movie(item,self._server))
            return movies
        elif self.CollectionType.lower() == 'tvshows':
            shows = []
            for item in data.get('Items'):
                shows.append(Movie(item,self._server))
            return shows
        else:
            raise MediaTypeError('只支持电影和剧集')

class Media(Util):
    def __init__(self,data,server) -> None:
        self.data = data
        self._server = server
        self._loaddata()

    def _loaddata(self):
        self.Name = self.data.get('Name')
        self.ServerId = self.data.get('ServerId')
        self.Id = self.data.get('Id')
        self.UserData = self.data.get('UserData')
        self.Type = self.data.get('Type')
        if self.UserData:
            self.Played = self.UserData.get('Played')
        if isinstance(self,Movie):
            self.MediaType = self.data.get('MediaType')
            if self.UserData:
                self.PlaybackPositionTicks = self.UserData.get('PlaybackPositionTicks')
        elif isinstance(self,Show):
            if self.UserData:
                self.UnplayedItemCount = self.UserData.get('UnplayedItemCount')
    
    async def fetchitem(self):
        data = await self._fetchitem(self.Id)
        if not self.Name:
            self.data = data
            self._loaddata()
        self.OriginalTitle = data.get('OriginalTitle')
        self.Etag = data.get('Etag')
        self.SortName = data.get('SortName')
        self.ForcedSortName = data.get('ForcedSortName')
        self.People = data.get('People')
        self.ProviderIds = data.get('ProviderIds')
        for k,v in self.ProviderIds.items():
            if 'tmdb' == k.lower():
                self.tmdb = 'tmdb://' + v if v else None
                self.tmdbid = v if v else None
            elif 'imdb' == k.lower():
                self.imdb = 'imdb://' + v if v else None
                self.imdbid = v if v else None
            elif 'tvdb' == k.lower():
                self.tvdb = 'tvdb://' + v if v else None
                self.tvdbid = v if v else None
        self.RecursiveItemCount = data.get('RecursiveItemCount')
        self.RunTimeTicks = data.get('RunTimeTicks')
        self.People = data.get('People')
        self.UserData = self.data.get('UserData')
        if self.UserData.get("LastPlayedDate"):
            self.LastPlayedDate = datetime.fromisoformat(self.UserData.get("LastPlayedDate")[:-1])

class Movie(Media):
    def __init__(self, data, server) -> None:
        super().__init__(data, server)

class Show(Media):
    def __init__(self, data, server) -> None:
        super().__init__(data, server)

    def check_played(self):
        if hasattr(self,'TotalRecordCount'):
            if self.UnplayedItemCount == self.TotalRecordCount:
                return False
            else:
                return True
        else:
            raise AsyncError('调用此函数前请调用self.epiodes')
        
    async def seasons(self):
        path = f'/Shows/{self.Id}/Seasons?UserId={self._server.userid}'
        data = await self._server.query(path)
        ses = []
        for se in data['Items']:
            ses.append(Season(se,self._server))
        return ses

    async def episodes(self):
        path = f'/Shows/{self.Id}/Episodes'
        payload = {'UserId': self._server.userid}
        url = self.bulidurl(path,payload)
        data = await self._server.query(url)
        self.TotalRecordCount = data.get('TotalRecordCount')
        eps = []
        for ep in data['Items']:
            eps.append(Episode(ep,self._server))
        return eps

    async def episode(self,season_num:int=None,episode_num:int=None):
        if season_num or episode_num:
            eps = await self.episodes()
            for ep in eps:
                if ep.ParentIndexNumber == season_num and ep.IndexNumber == episode_num:
                    return ep
            return None
        #else:
        raise InvalidParams('请传入合法参数')

class Season(Util):
    def __init__(self,data,server) -> None:
        self.data = data
        self._server = server
        self._loaddata()
    
    def _loaddata(self):
        self.Id = self.data.get('Id')
        self.IndexNumber = self.data.get('IndexNumber')
        self.Name = self.data.get('Name')
        self.SeriesId = self.data.get('SeriesId')
        self.SeriesName = self.data.get('SeriesName')
        self.Type = self.data.get('Type')
        self.UserData = self.data.get('UserData')
        self.Played = self.UserData.get('Played')
        self.UnplayedItemCount = self.UserData.get('UnplayedItemCount')

    async def episodes(self):
        path = f'/Shows/{self.SeriesId}/Episodes'
        payload = {'UserId': self._server.userid,'SeasonId':self.Id}
        url = self.bulidurl(path,payload)
        data = await self._server.query(url)
        eps = []
        for ep in data['Items']:
            eps.append(Episode(ep,self._server))
        return eps

class Episode(Util):
    def __init__(self,data,server) -> None:
        self.data = data
        self._server = server
        self._loaddata()

    def _loaddata(self):
        self.Name = self.data.get('Name')
        self.Id = self.data.get('Id')
        self.ParentIndexNumber = self.data.get('ParentIndexNumber')
        self.IndexNumber = self.data.get('IndexNumber')
        self.Type = self.data.get('Type')
        self.UserData = self.data.get('UserData')
        self.PlaybackPositionTicks = self.UserData.get('PlaybackPositionTicks')
        self.Played = self.UserData.get('Played')
        self.SeriesName = self.data.get('SeriesName')
        self.SeriesId = self.data.get('SeriesId')
        self.SeasonId = self.data.get('SeasonId')

    async def reload(self):
        await self.fetchitem()

    async def fetchitem(self):
        data = await self._fetchitem(self.Id)
        self.data = data
        self._loaddata()
        if self.UserData.get('LastPlayedDate'):
            self.LastPlayedDate = datetime.fromisoformat(self.UserData.get('LastPlayedDate')[:-1])

    async def GetShow(self):
        data = {'Id':self.SeriesId}
        parent_show = Show(data,self._server)
        await parent_show.fetchitem()
        return parent_show