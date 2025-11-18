import aiohttp
import asyncio
from functools import wraps
from util.util import Util
from util.log import log
from util.exception import MediaTypeError,AsyncError,InvalidParams
from datetime import datetime

def require_login(func):
    """装饰器：确保方法执行前已登录，失败时自动重试登录"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # 检查是否需要登录
        if not hasattr(self, 'token') or not self.token:
            if not hasattr(self, 'uname') or not hasattr(self, 'pw'):
                raise InvalidParams(f'{func.__name__}: 未提供登录凭据，无法自动登录')

            try:
                log.info(f'{func.__name__}: 尝试登录...')
                await self.login()
            except Exception as e:
                log.error(f'{func.__name__}: 登录失败')
                raise AsyncError(f'{func.__name__}: 登录失败，请检查网络或账密: {str(e)}')

        # 执行原方法
        return await func(self, *args, **kwargs)
    return wrapper

class Jellyfinserver(Util):
    def __init__(self,jf_url,jf_token=None,username=None,password=None) -> None:
        if username and password:
            self.uname = username
            self.pw = password
            self.token = None  # 初始化为 None，需要登录
        else:
            self.token = jf_token
            self.header = {'X-Emby-Token': jf_token,"accept": "application/json"}
        self.url = jf_url.rstrip('/')
        self.userid = None
        self._login_lock = asyncio.Lock()  # 防止并发登录
        self.type = 'jellyfin'
        self._server = self

    async def login(self):
        """登录到 Jellyfin 服务器，带重试和错误处理"""
        async with self._login_lock:  # 防止并发登录
            if not hasattr(self,'session'):
                self.session = aiohttp.ClientSession()

            if not hasattr(self, 'uname') or not hasattr(self, 'pw'):
                raise InvalidParams('未提供用户名和密码，无法登录')

            header = {'x-emby-authorization':
                'Emby UserId="python",'
                'Client="python",'
                'Device="Embypretty",'
                'DeviceId="jf_0910",'
                'Version="1.0.1"'}
            payload = {
                'Username':self.uname,
                'Pw':self.pw
            }
            self.header = header

            try:
                data = await self.query("/Users/AuthenticateByName",method='POST',headers=self.header,
                                        json=payload,
                                        msg='登录失败，请检查账密或网络')
                self.token = data.get('AccessToken')
                self.userid = data['User'].get('Id')
                self.header = {'X-Emby-Token': self.token,"accept": "application/json"}
                log.info(f'Jellyfin 服务器登录成功: {self.url}')
            except Exception as e:
                log.error(f'Jellyfin 服务器登录失败: {self.url}, 错误: {str(e)}')
                raise
    @require_login
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
    @require_login
    async def test_connection(self, timeout: float = 5.0) -> bool:
        """测试服务器连接是否正常

        Args:
            timeout: 超时时间（秒），默认 5 秒
        """
        try:
            import asyncio
            if self.userid:
                path = f'/Users/{self.userid}'
            else:
                path = self.bulidurl('/System/Info', {'api_key': self.token})

            # 添加超时限制
            await asyncio.wait_for(
                self.query(path, msg='连接测试失败'),
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            log.warning(f"Jellyfin 服务器 {getattr(self, 'name', 'Unknown')} 连接超时 ({timeout}秒)")
            return False
        except Exception as e:
            log.error(f"Jellyfin 服务器连接测试异常: {e}")
            return False

    @require_login
    async def guidsearch(self,tmdb:str=None,tvdb:str=None,imdb:str=None):
        path = f'/Search/Hints'
        search_key = ''
        search_key += 'tmdb.'+ tmdb if tmdb else ''
        search_key += ',tvdb.'+ tvdb if tvdb else ''
        search_key += ',imdb.'+ imdb if imdb else ''
        payload = {
            'UserId':self.userid,
            'Recursive': True,
            'searchTerm': tmdb,
            #"Fields":"UserData,OriginalTitle,Etag,SortName,ForcedSortName,ProviderIds,RecursiveItemCount,RunTimeTicks"
            "Fields":"UserData,ProviderIds,UserDataLastPlayedDate",
            'IncludeItemTypes': "Movie,Series"
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

    @require_login
    async def hub_continue(self):
        if not self.userid:
            raise InvalidParams('hub_continue: 此方法需要用户ID，请使用用户名和密码登录（不支持仅使用 API Token）')
        payload = {
            'Recursive':True,
            "Fields":"UserData,ProviderIds,UserDataLastPlayedDate"
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
            log.warning(f'Jellyfin({self.name})无继续观看记录')
        return medias

    @require_login
    async def history(self,**kwargs):
        if not self.userid:
            raise InvalidParams('history: 此方法需要用户ID，请使用用户名和密码登录（不支持仅使用 API Token）')
        if kwargs:
            payload = kwargs
        else:
            payload = {
                'IsPlayed': True,
                'SortBy':'DatePlayed',
                'SortOrder':'Descending',
                'Recursive':True,
                'Limit':20,
                "Fields":"UserData,ProviderIds,UserDataLastPlayedDate"
            }
        path = self.bulidurl(f'/Users/{self.userid}/Items',payload)
        data = await self._server.query(path,msg='请求历史失败')
        medias = []
        if data.get('TotalRecordCount') == 0:
            log.warning('Jellyfin无历史播放记录')
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

    async def get_library_by_id(self,lib_id):
        libs = await self.library()
        for lib in libs:
            if lib.Id == lib_id:
                return lib
        return None

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