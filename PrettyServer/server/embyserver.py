import aiohttp
from util.util import Util
from util.log import log
from util.exception import MediaTypeError,AsyncError,InvalidParams
from datetime import datetime

class Embyserver(Util):
    def __init__(self,emby_url,emby_token=None,username=None,password=None) -> None:
        if username and password:
            self.uname = username
            self.pw = password
        else:
            self.token = emby_token
            self.header = {'X-Emby-Token': emby_token,"accept": "application/json"}
        self.url = emby_url.rstrip('/')
        self.userid = None
        if self.url.split('/')[-1] != 'emby':
            self.url += '/emby'
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
        if self.userid:
            path = f'/Users/{self.userid}/Views'
        else:
            path = "/Library/MediaFolders"
        data = await self.query(path,msg='请求错误')
        librarys = []
        for lb in data['Items']:
            if lb.get("CollectionType"):
                if lb.get("CollectionType") == "tvshows":
                    librarys.append(SeriesLibrary(lb,self._server))
                elif lb.get("CollectionType") == "movies":
                    librarys.append(MovieLibrary(lb,self._server))
                else:
                    librarys.append(Library(lb,self._server))
            else:
                librarys.append(MixContent(lb,self._server))
        return librarys

    async def close(self):
        if hasattr(self,"session"):
            await self.session.close()

    async def guidsearch(self,tmdb:str=None,tvdb:str=None,imdb:str=None):
        path = f'/Items'
        search_key = ''
        search_key += 'tmdb.'+ tmdb if tmdb else ''
        search_key += ',tvdb.'+ tvdb if tvdb else ''
        search_key += ',imdb.'+ imdb if imdb else ''
        payload = {
            'UserId':self.userid,
            'Recursive': True,
            'AnyProviderIdEquals': search_key,
            #"Fields":"UserData,OriginalTitle,Etag,SortName,ForcedSortName,ProviderIds,RecursiveItemCount,RunTimeTicks"
            "Fields":"UserData,ProviderIds,UserDataLastPlayedDate",
            'IncludeItemTypes': "Movie,Series"
        }
        if not self.userid:
            payload.pop("UserId")
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
        if not self.userid:
            raise InvalidParams("Emby没有登录，无法查询继续观看")
        payload = {
            'Recursive':True,
            "Fields":"UserData,ProviderIds,UserDataLastPlayedDate",
            'MediaTypes': 'Video',
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
                    item['UserData'].get("LastPlayedDate")[:-2])
                medias.append(media)
        if not medias:
            log.warning(f'Emby({self.name})无继续观看记录')
        return medias

    async def history(self,**kwargs):
        if not self.userid:
            raise InvalidParams("Emby没有登录，无法查询历史记录")
        if kwargs:
            payload = kwargs
        else:
            payload = {
                'IsPlayed': True,
                'SortBy':'DatePlayed',
                'SortOrder':'Descending',
                'Recursive':True,
                'Limit':20,
                "Fields":"UserData,ProviderIds,UserDataLastPlayedDate",
                'MediaTypes': 'Video',
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
                    item['UserData'].get("LastPlayedDate")[:-2])
                medias.append(media)
        return medias

    async def get_person(self):
        path = "/Persons"
        payload = {
            "Fields":"ProviderIds"
        }
        data = await self._server.query(self.bulidurl(path,payload))
        for person in data.get("Items"):
            yield Person(person,self._server)

    async def part_refresh(self, scan_path):
        path = "/Library/Media/Updated"
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        payload = {"Updates": [{"Path": f"{scan_path}", "UpdateType": "Created"}]}
        await self.query(path,method="post",json=payload,headers=headers,msg=f'{self.name}: 刷新路径 {scan_path} 失败')

    async def merge_version(self,ids:list):
        payload = {
            'Ids':','.join(ids)
        }
        path = self.bulidurl(f'/Videos/MergeVersions',payload)
        await self.query(path,method='post',msg='合并失败')

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
        #boxsets:合集；tvshows：剧集；movies：电影；None:混合内容;audiobooks:有声书
        #games：游戏，homevideos：家庭影库；music：音乐；musicvideos：MV
        self.CollectionType = self.data.get('CollectionType')

    async def fetchitems(self,**kwargs):
        if self._server.userid:
            path = f'/Users/{self._server.userid}/Items'
        else:
            path = f'/Items'
        payload = kwargs
        url = self.bulidurl(path,payload)
        data = await self._server.query(url)
        return data
    
    async def all(self):
        data = await self.fetchitems(Recursive=True,ParentId=self.Id,
                                     IncludeItemTypes="Movie,Series",
                                     Fields="UserData,OriginalTitle,Etag,SortName,ForcedSortName,ProviderIds,RecursiveItemCount,RunTimeTicks,UserDataLastPlayedDate")
        if data.get('Items') == None:
            return []
        if self.CollectionType == None:
            media = []
            for item in data.get('Items'):
                if item.get("Type") == "Movie":
                    media.append(Movie(item,self._server))
                elif item.get("Type") == "Series":
                    media.append(Show(item,self._server))
                else:
                    log.warning(f"{self.Name} 发现{item.get('Name')} 非电影或剧集")
            return media
        elif self.CollectionType.lower() == 'movies':
            movies = []
            for item in data.get('Items'):
                movies.append(Movie(item,self._server))
            return movies
        elif self.CollectionType.lower() == 'tvshows':
            shows = []
            for item in data.get('Items'):
                shows.append(Show(item,self._server))
            return shows
        else:
            raise MediaTypeError('只支持电影、剧集和混合内容库')

    async def refresh(self):
        path = f"/items/{self.Id}/Refresh"
        payload = {
            "Recursive": "true",
            "ImageRefreshMode": "Default",
            "MetadataRefreshMode": "Default",
            "ReplaceAllImages": "false",
            "ReplaceAllMetadata" :"false"
        }
        await self._server.query(self.bulidurl(path,payload),'post',msg=f'{self.Name} 刷新媒体库失败')

#混合内容增加方法：获取电影和获取剧集
class MixContent(Library):
    def __init__(self, data, server) -> None:
        super().__init__(data, server)
    #获取混合内容的电影
    async def get_movie(self):
        data = await self.fetchitems(Recursive=True,ParentId=self.Id,
                                     IncludeItemTypes="Movie",
                                     Fields="UserData,OriginalTitle,Etag,SortName,ForcedSortName,ProviderIds,RecursiveItemCount,RunTimeTicks,UserDataLastPlayedDate")
        if data.get('Items') == None:
            return []
        media = []
        for item in data.get('Items'):
            media.append(Movie(item,self._server))
        return media
    #获取混合内容的剧集
    async def get_series(self):
        data = await self.fetchitems(Recursive=True,ParentId=self.Id,
                                     IncludeItemTypes="Series",
                                     Fields="UserData,OriginalTitle,Etag,SortName,ForcedSortName,ProviderIds,RecursiveItemCount,RunTimeTicks,UserDataLastPlayedDate")
        if data.get('Items') == None:
            return []
        media = []
        for item in data.get('Items'):
            media.append(Show(item,self._server))
        return media

class MovieLibrary(Library):
    def __init__(self, data, server) -> None:
        super().__init__(data, server)

class SeriesLibrary(Library):
    def __init__(self, data, server) -> None:
        super().__init__(data, server)

    async def get_all_seasons(self):
        seasons = []
        data = await self.fetchitems(Recursive=True,ParentId=self.Id,
                                     IncludeItemTypes="Season",
                                     Fields="UserData,OriginalTitle,Etag,SortName,ForcedSortName,ProviderIds,RecursiveItemCount,RunTimeTicks,UserDataLastPlayedDate")
        for season in data.get("Items"):
            seasons.append(Season(season,self._server))
        return seasons

class Media(Util):
    def __init__(self,data,server) -> None:
        self.data = data
        self._server = server
        self._loaddata()
    #加载媒体对应属性
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
        self.OriginalTitle = self.data.get('OriginalTitle')
        self.Etag = self.data.get('Etag')
        self.SortName = self.data.get('SortName')
        self.ForcedSortName = self.data.get('ForcedSortName')
        self.People = self.data.get('People')
        self.ProviderIds = self.data.get('ProviderIds')
        self.tmdb = self.tmdbid = self.imdb = self.imdbid = self.tvdb = self.tvdbid = None
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
        self.RecursiveItemCount = self.data.get('RecursiveItemCount')
        self.RunTimeTicks = self.data.get('RunTimeTicks')
        if self.UserData:
            if self.UserData.get("LastPlayedDate"):
                self.LastPlayedDate = datetime.fromisoformat(self.UserData.get("LastPlayedDate")[:-2])
    #刷新重载媒体数据
    async def fetchitem(self):
        data = await self._fetchitem(self.Id)
        self.data = data
        self._loaddata()
    
    async def edit(self,data):
        payload = {"reqformat":"json"}
        path = f"/Items/{self.Id}"
        await self._server.query(self.bulidurl(path,payload),method='post',json=data)

    async def reload(self):
        await self.fetchitem()

class Movie(Media):
    def __init__(self, data, server) -> None:
        super().__init__(data, server)

class Show(Media):
    def __init__(self, data, server) -> None:
        super().__init__(data, server)
    
    #检查剧集是否播放过
    def check_played(self):
        if hasattr(self,'TotalRecordCount'):
            if self.UnplayedItemCount == self.TotalRecordCount:
                return False
            else:
                return True
        else:
            raise AsyncError('调用此函数前请调用self.epiodes')
    #获取剧集季
    async def seasons(self):
        path = f'/Shows/{self.Id}/Seasons?UserId={self._server.userid}'
        data = await self._server.query(path)
        ses = []
        for se in data['Items']:
            ses.append(Season(se,self._server))
        return ses
    #获取剧集集
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
    #获取特定集
    async def episode(self,season_num:int=None,episode_num:int=None):
        if season_num or episode_num:
            eps = await self.episodes()
            for ep in eps:
                if ep.ParentIndexNumber == season_num and ep.IndexNumber == episode_num:
                    return ep
            return None
        #else:
        raise InvalidParams('请传入合法参数')

class Season(Media):
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

    async def GetShow(self):
        data:dict = self.data
        data.update({'Id':self.SeriesId})
        parent_show = Show(data,self._server)
        await parent_show.fetchitem()
        return parent_show

    async def episodes(self):
        path = f'/Shows/{self.SeriesId}/Episodes'
        payload = {'UserId': self._server.userid,'SeasonId':self.Id}
        if not self._server.userid:
            payload.pop("UserId")
        url = self.bulidurl(path,payload)
        data = await self._server.query(url)
        eps = []
        for ep in data['Items']:
            eps.append(Episode(ep,self._server))
        return eps

    async def fetchitem(self):
        data = await self._fetchitem(self.Id)
        self.data = data
        self._loaddata()

    async def reload(self):
        await self.fetchitem()

class Episode(Media):
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

    async def fetchitem(self):
        data = await self._fetchitem(self.Id)
        self.data = data
        self._loaddata()
        if self.UserData:
            if self.UserData.get('LastPlayedDate'):
                self.LastPlayedDate = datetime.fromisoformat(self.UserData.get('LastPlayedDate')[:-2])

    async def GetShow(self):
        data:dict = self.data
        data.update({'Id':self.SeriesId})
        parent_show = Show(data,self._server)
        await parent_show.fetchitem()
        return parent_show

class Person(Media):
    def __init__(self,data,server) -> None:
        self.data = data
        self._server = server
        self._loaddata()
    
    def _loaddata(self):
        self.Name = self.data.get("Name")
        self.ServerId = self.data.get("ServerId")
        self.Id = self.data.get("Id")
        self.Type = self.data.get("Type")
        self.Name = self.data.get("Name")
        self.ProviderIds = self.data.get('ProviderIds')
        self.tmdb = self.tmdbid = self.imdb = self.imdbid = self.tvdb = self.tvdbid = None
        if self.ProviderIds != None:
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