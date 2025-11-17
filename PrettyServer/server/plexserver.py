import aiohttp
import re
import time
from platform import uname
from uuid import getnode
from util.util import Util
from util.exception import AsyncError,InvalidParams,FailRequest,MediaTypeError
from util.log import log

class Plexserver(Util):

    def __init__(self,plex_url:str,plex_token:str):
        self.header = {'X-Plex-Token': plex_token,
                       "accept": "application/json",
                        'X-Plex-Platform': uname()[0],
                        'X-Plex-Platform-Version': uname()[2],
                        'X-Plex-Provides': 'controller',
                        'X-Plex-Product': 'PlexPretty',
                        'X-Plex-Version': '1.0.0',
                        'X-Plex-Device': uname()[0],
                        'X-Plex-Device-Name': uname()[1],
                        'X-Plex-Client-Identifier': str(hex(getnode())),
                        'X-Plex-Sync-Version': '2',
                        'X-Plex-Features': 'external-media',
                        }
        self.url = plex_url.rstrip('/')
        self.type = 'plex'
        self._server = self

    async def library(self):
        if not hasattr(self,'session'):
            self.session = aiohttp.ClientSession()
        data = await self.query('/library/sections/',msg='请求失败，请检查网络或Plex地址和Token')
        return Library(data,self._server)

    async def hub_continue(self):
        data = await self._server.query('/hubs/home/continueWatching')
        medias = []
        if data['MediaContainer'].get('size') == 0:
            log.warning(f'Plex({self.name})主界面没有继续观看')
        else:
            for item in data['MediaContainer'].get('Metadata'):
                if item.get('type').lower() == 'movie':
                    medias.append(Movie(item,self._server))
                elif item.get('type').lower() == 'episode':
                    medias.append(Episode(item,self._server))
        return medias

    async def history(self,**kwargs):
        if kwargs:
            payload = kwargs
        else:
            payload = {
                'sort':'viewedAt:desc',
                'viewedAt>': int(time.time() - 604800),
                'accountID': 1
            }
        path = self.bulidurl('/status/sessions/history/all',payload)
        try:
            data = await self._server.query(path,msg='请求历史失败')
            medias = []
            if data['MediaContainer'].get('size') == 0:
                log.warning(f'Plex({self.name})无历史播放记录')
            else:
                for item in data['MediaContainer'].get('Metadata'):
                    if item.get('type').lower() == 'movie':
                        medias.append(Movie(item,self._server))
                    elif item.get('type').lower() == 'episode':
                        medias.append(Episode(item,self._server))
            return medias
        except FailRequest:
            medias = await self._history()
            return medias

    async def _history(self):
        lb = await self.library()
        medias = []
        for section in lb.sections():
            media = await section.history()
            if media:
                medias += media
        sort_medias = sorted(medias,key = lambda x:x.lastViewedAt
                             ,reverse=True)
        if len(sort_medias) > 20:
            return sort_medias[:20]
        else:
            return sort_medias
        
    async def guidsearch(self,tmdb:str=None,tvdb:str=None,imdb:str=None):
        lb = await self.library()
        medias = []
        for section in lb.sections():
            if tmdb:
                media = await section._guidsearch(f"tmdb://{tmdb}")
                if media:
                    medias.append(media)
                    continue
            if tvdb:
                media = await section._guidsearch(f"tvdb://{tvdb}")
                if media:
                    medias.append(media)
                    continue
            if imdb:
                media = await section._guidsearch(f"imdb://{imdb}")
                if media:
                    medias.append(media)
                    continue
                
        return medias
    #close plex aio session
    async def close(self):
        if hasattr(self,"session"):
            await self.session.close()

    async def test_connection(self, timeout: float = 5.0) -> bool:
        """测试服务器连接是否正常

        Args:
            timeout: 超时时间（秒），默认 5 秒
        """
        try:
            import asyncio
            # 使用 /library/sections 测试连接，添加超时限制
            await asyncio.wait_for(
                self.query('/library/sections/', msg='连接测试失败'),
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            log.warning(f"Plex 服务器 {getattr(self, 'name', 'Unknown')} 连接超时 ({timeout}秒)")
            return False
        except Exception as e:
            log.error(f"Plex 服务器连接测试异常: {e}")
            return False

class Library(Util):
    
    def __init__(self,data,server):
        self.data = data
        self._server = server
        self._sections = []
        self._loaddata()

    def _loaddata(self):
        pass
    #get all section return object Section
    def sections(self):
        for section in self.data['MediaContainer']['Directory']:
            self._sections.append(Section(section,self._server))
        return self._sections

class Section(Util):  

    def __init__(self,data,server) -> None:
        self._server = server
        self.key = data['key']
        self.type = data['type']
        self.title = data['title']
        self.agent = data.get('agent')

    #get all media for a specific setion
    async def all(self):
        medias = []
        data = await self._server.query(f'/library/sections/{self.key}/all')
        self._totalsize = data['MediaContainer']['size']
        if self._totalsize > 0:
            for media in data['MediaContainer']['Metadata']:
                if self.type.lower() == 'show':
                    medias.append(Show(media,self._server))
                elif self.type.lower() == 'movie':
                    medias.append(Movie(media,self._server))
        return medias
    
    async def _guidsearch(self,guid):
        if guid.startswith('plex://'):
            data = await self._server.query(f'/library/sections/{self.key}/all?guid={guid}')
        else:
            data = await self._server.query(f'/library/sections/{self.key}/all?X-Plex-Container-Size=1&X-Plex-Container-Start=0')
            if data['MediaContainer'].get('Metadata'):
                ekey = data['MediaContainer']['Metadata'][0].get('ratingKey')
                format_guid = guid.replace('://', '-')
                data = await self._server.query(f'/library/metadata/{ekey}/matches?manual=1&title={format_guid}&agent={self.agent}')
                if data['MediaContainer'].get('SearchResult'):
                    plex_guid = data['MediaContainer']['SearchResult'][0].get('guid')
                else:
                    plex_guid = 0
                data = await self._server.query(f'/library/sections/{self.key}/all?guid={plex_guid}')
        item_data = data['MediaContainer'].get('Metadata')
        if item_data:
            if self.type == 'show':
                return Show(item_data[0],self._server)
            elif self.type == 'movie':
                return Movie(item_data[0],self._server)
            
    async def history(self):
        if self.type.lower() == 'show':
            type = 4
        elif self.type.lower() == 'movie':
            type = 1
        else:
            raise MediaTypeError
        payload = {
            'sort': 'lastViewedAt:desc',
            'unwatched': '0',
            'viewOffset': '0',
            'type': type,
            'X-Plex-Container-Start': '0',
            'X-Plex-Container-Size': '20'
        }
        path = self.bulidurl(f'/library/sections/{self.key}/all',payload)
        data = await self._server.query(path)
        medias = []
        if data['MediaContainer'].get('Metadata'):
            for item in data['MediaContainer'].get('Metadata'):
                if self.type == 'show':
                    medias.append(Episode(item,self._server))
                elif self.type == 'movie':
                    medias.append(Movie(item,self._server))
            return medias
    #刷新媒体库
    async def part_refresh(self,scan_path):
        path = f"/library/sections/{self.key}/refresh"
        para = {
            "path": scan_path
        }
        await self._server.query(self.bulidurl(path,para),msg=f'{self.name}: 刷新路径 {scan_path} 失败')

    async def refresh(self):
        path = f"/library/sections/{self.key}/refresh"
        await self._server.query(path,msg=f'{self.title}: 刷新媒体库失败')

class Media(Util):

    #load some attr for some Media(Just Show and Movie)
    def _loaddata(self):
        self.title = self.data.get('title')
        self.ratingKey = self.data.get('ratingKey')
        #Show:key:"/library/metadata/2498/children"
        #Movie:key:"/library/metadata/1109"
        self.key = self.data.get('key')
        self.originalTitle = self.data.get('originalTitle')
        self.titleSort = self.data.get('titleSort')
        self.type = self.data.get('type')
        self.viewCount = self.data.get('viewCount')
        self.lastViewedAt = self.data.get('lastViewedAt')
        self.viewedAt = self.data.get('viewedAt')
        self.tmdb = self.tmdbid = self.imdb = self.imdbid = self.tvdb = self.tvdbid = None
        if self.type:
            if self.type.lower() == 'movie':
                self.duration = self.data.get('duration')
                self.viewOffset = self.data.get('viewOffset')
            elif self.type.lower() == 'show':
                self.viewedLeafCount = self.data.get('viewedLeafCount')
                self.leafCount = self.data.get('leafCount')

    #Get more data for a specific media
    async def fetchitem(self):
        data = await self._fetchitem(self.ratingKey)
        if not self.title:
            self.data = data['MediaContainer']['Metadata'][0]
            self._loaddata()
        self.guid = data['MediaContainer']['Metadata'][0].get('Guid')
        try:
            for guid in self.guid:
                if 'tmdb' in guid.get('id').lower():
                    self.tmdb = guid.get('id')
                    self.tmdbid = re.findall(r'\d+',guid.get('id'),re.S)[0]
                elif 'imdb' in guid.get('id').lower():
                    self.imdb = guid.get('id')
                    self.imdbid = re.findall(r'\d+',guid.get('id'),re.S)[0]
                elif 'tvdb' in guid.get('id').lower():
                    self.tvdb = guid.get('id')
                    self.tvdbid = re.findall(r'\d+',guid.get('id'),re.S)[0]
        except:
            log.warning(f'{self.title} do not have guid')
        self._Role = data['MediaContainer']['Metadata'][0].get('Role')
        self.Country = data['MediaContainer']['Metadata'][0].get('Country')
        self.Genre = data['MediaContainer']['Metadata'][0].get('Genre')
        self.Field = data['MediaContainer']['Metadata'][0].get('Field')
        self.lastViewedAt = data['MediaContainer']['Metadata'][0].get('lastViewedAt')
        #/library/sections/8
        self.librarySectionKey = data['MediaContainer']['Metadata'][0].get('librarySectionKey')
        self.librarySectionTitle = data['MediaContainer'].get('librarySectionTitle')
        self.librarySectionID = data['MediaContainer'].get('librarySectionID')
        self.librarySectionUUID = data['MediaContainer'].get('librarySectionUUID')
        if self.type.lower() == 'show':
            self.Location = data['MediaContainer']['Metadata'][0].get('Location')
            self.childCount = data['MediaContainer']['Metadata'][0].get('childCount')

    #get all Role about the media
    def roles(self):
        if not hasattr(self,'_Role'):
            raise AsyncError('使用此方法前请调用异步方法fetchitem')
        roles = []
        for role in self._Role:
            roles.append(Role(role,self._server,self.librarySectionID))
        return roles

    #A method to edit the tag of the ekey media
    async def edit_role(self,actors):
        i = 0
        replace = []
        for actor in actors:
            replace.append(f'actor[{i}].tag.tag={actor.tag}' +
                            f'&actor[{i}].tagging.text={actor.role}' +
                            f'&actor[{i}].tag.thumb={actor.thumb}' +
                            f'&actor[{i}].tag.tagKey={actor.tagKey}')
            i += 1
        replace_actor = str.join("&", replace)
        part = f'/library/metadata/{self.ratingKey}?{replace_actor}'
        data = await self._server.query(part, method='put')
        return data

    #A method to edit the titlesort of the ekey media
    async def edit_titlesort(self,value,lock=0):
        if self.type.lower() == 'show':
            type = 2
        elif self.type.lower() == 'movie':
            type = 1
        para = f"id={self.ratingKey}" + f'&type={type}'+ f'&titleSort.value={value}'+f'&titleSort.locked={lock}'
        path = f'/library/sections/{self.librarySectionID}/all'
        data = await self._server.query(path+'?'+para,method='put')
        return data

    async def reload(self):
        await self.fetchitem()

class Movie(Media):
    def __init__(self,data,server):
        self._server = server
        self.data = data
        #self.Location = self.data['Metadata'][0].get('Location')
        self._loaddata()

class Show(Media):

    def __init__(self,data,server):
        self._server = server
        self.data = data
        self._loaddata()

    #get all seasons about one show return object Season
    async def seasons(self):
        data = await self._server.query(self.key)
        _seasons = []
        for season in data['MediaContainer']['Metadata']:
            _seasons.append(Season(season,self._server))
        return _seasons

    #get all seasons about one show return object Episode
    async def episodes(self):
        path = f'{self.ratingKey}/allLeaves'
        data = await self._fetchitem(path)
        eps = []
        for ep in data['MediaContainer']['Metadata']:
            eps.append(Episode(ep,self._server))
        return eps
    
    #get specfic episode
    async def episode(self,season_num:int=None,episode_num:int=None):
        if season_num or episode_num:
            eps = await self.episodes()
            for ep in eps:
                if ep.parentIndex == season_num and ep.index == episode_num:
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
        self.index = self.data.get('index')
        self.guid = self.data.get('guid')
        self.key = self.data.get('key')
        self.leafCount = self.data.get('leafCount')
        self.parentKey = self.data.get('parentKey')
        self.parentRatingKey = self.data.get('parentRatingKey')
        self.parentTitle = self.data.get('parentTitle')
        self.ratingKey = self.data.get('ratingKey')
        self.title = self.data.get('title')
        self.type = self.data.get('type')

    async def episodes(self):
        path = f'{self.ratingKey}/children/allLeaves'
        data = await self._fetchitem(path)
        eps = []
        for ep in data['MediaContainer']['Metadata']:
            eps.append(Episode(ep,self._server))
        return eps

class Episode(Util):
    def __init__(self,data,server):
        self.data = data
        self._server = server
        self._loaddata()

    def _loaddata(self):
        self.Media = self.data.get('Media')
        self.key = self.data.get('key')
        self.duration = self.data.get('duration')
        self.viewCount = self.data.get('viewCount')
        self.viewOffset = self.data.get('viewOffset')
        self.type = self.data.get('type')
        self.ratingKey = self.data.get('ratingKey')
        self.title = self.data.get('title')
        self.parentTitle = self.data.get('parentTitle')
        self.grandparentTitle = self.data.get('grandparentTitle')
        self.parentIndex = self.data.get('parentIndex')
        self.index = self.data.get('index')
        self.lastViewedAt = self.data.get('lastViewedAt')
        self.viewedAt = self.data.get('viewedAt')
        self.parentRatingKey = self.data.get('parentRatingKey')
        self.grandparentRatingKey = self.data.get('grandparentRatingKey')
        self.grandparentKey = self.data.get('grandparentKey')

    async def GetShow(self):
        if self.grandparentRatingKey:
            data = {'ratingKey':self.grandparentRatingKey}
        else:
            data = {'ratingKey':self.grandparentKey.split('/')[-1]}
        parent_show = Show(data,self._server)
        await parent_show.fetchitem()
        return parent_show

class Role(Util):
#{'id': 466, 'filter': 'actor=466', 'tag': 'Amy Parrish', 'tagKey': '5d776835e6d55c002040d22d', 'role': 'Judy Cohen', 'thumb': 'https://metadata-static.plex.tv/people/5d776835e6d55c002040d22d.jpg'}
    def __init__(self,data,server,librarySectionID) -> None:
        self._server = server
        self.data = data
        self.librarySectionID = librarySectionID
        self._loaddata()
    
    def _loaddata(self):
        self.id = self.data.get('id')
        self.filter = self.data.get('filter')
        self.tag = self.data.get('tag')
        self.tagKey = self.data.get('tagKey')
        self.thumb = self.data.get('thumb','')
        self.role = self.data.get('role')

class User(Util):
    def __init__(self,data,server) -> None:
        self.data = data
        self._server = server
