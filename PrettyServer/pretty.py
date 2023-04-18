import asyncio
import aiohttp
import sys
import re
import os
import traceback
from datetime import datetime
from platform import uname
from uuid import getnode
from pypinyin import pinyin, Style
from loguru import logger as log

PLEX_TOKEN = "z21kxbGraX5yByjkkZ8g"
PLEX_URL = "http://127.0.0.1:32400"
TMDB_API_KEY = '26edbd25d692245d1a8c2e6ac07cca06'
#是否使用代理，是True，否False
ISPROXY = False
#代理地址
PROXY = 'http://127.0.0.1:7890'
LOG_PATH = sys.path[0]
#并发数，默认1000
CONCURRENT_NUM = 1000

class MediaTypeError(Exception):
    def __init__(self, type):
        self.type = type

class FailRequest(Exception):
    pass

class Util():
    async def _fetchitem(self,ekey):
        """
            ekey : ratingKey
        """
        path_url = f'/library/metadata/{ekey}'
        data = await self._server.query(path_url)
        return data

class Plexserver():

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
        self.session = aiohttp.ClientSession()
        self._server = self


    async def query(self, path, method=None, headers=None, timeout=None, **kwargs):
        url = self.url + path
        if headers:
            header = self.header
            header.update(headers)
        if method is not None:
            if method.upper() == 'POST':
                async with self.session.post(url,headers=self.header) as res:
                    if res.status in (200, 201, 204):
                        data = await res.json()
                    else:
                        raise FailRequest
                #headers.update({'Content-type': 'application/x-www-form-urlencoded'})
            elif method.upper() == 'PUT':
                async with self.session.put(url,headers=self.header) as res:
                    if res.status in (200, 201, 204):
                        data = res
                    else:
                        raise FailRequest
            elif method.upper() == 'DELETE':
                async with self.session.delete(url,headers=self.header) as res:
                    if res.status in (200, 201, 204):
                        data = await res.json()
                    else:
                        raise FailRequest
            else:
                #print("Invalid request method provided: {method}".format(method=method))
                return
        else:
            async with self.session.get(url,headers=self.header) as res:
                if res.status in (200, 201, 204):
                    data = await res.json()
                else:
                    raise FailRequest
        #log.debug('%s %s', method.__name__.upper(), url)
        return data

    async def library(self):
        data = await self.query('/library/sections/')
        return Library(data,self._server)

    async def close(self):
        await self.session.close()

class Library():
    
    def __init__(self,data,server):
        self.data = data
        self._server = server
        self._sections = []
        self._loaddata()

    def _loaddata(self):
        pass

    def sections(self):
        for section in self.data['MediaContainer']['Directory']:
            self._sections.append(Section(section,self._server))
        return self._sections

class Section():  

    def __init__(self,data,server) -> None:
        self._server = server
        self.key = data['key']
        self.type = data['type']
        self.title = data['title']

    async def all(self):
        medias = []
        data = await self._server.query(f'/library/sections/{self.key}/all')
        self._totalsize = data['MediaContainer']['size']
        for media in data['MediaContainer']['Metadata']:
            _media = Media(media,self._server)
            _media.librarySectionID = self.key
            medias.append(_media)
        return medias
    
class Media(Util):
    def __init__(self,data,server):
        self._server = server
        self.data = data
        self._loaddata()

    def _loaddata(self):
        self.ratingKey = self.data.get('ratingKey')
        self.title = self.data.get('title')
        self.titleSort = self.data.get('titleSort')
        self.type = self.data.get('type')

    async def fetchitem(self,ekey):
        data = await self._fetchitem(ekey)
        return Video(data,self._server)

    @property
    async def episodes(self):
        path = f'{self.ratingKey}/allLeaves'
        data = await self._fetchitem(path)
        return data

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

    async def edit_titlesort(self,value,lock=0):
        if self.type.lower() == 'show':
            type = 2
        elif self.type.lower() == 'movie':
            type = 1
        para = f"id={self.ratingKey}" + f'&type={type}'+ f'&titleSort.value={value}'+f'&titleSort.locked={lock}'
        path = f'/library/sections/{self.librarySectionID}/all'
        data = await self._server.query(path+'?'+para,method='put')
        return data

class Video():

    def __init__(self,data,server):
        self._server = server
        self.data = data
        self._loaddata()

    def _loaddata(self):
        self.title = self.data['MediaContainer']['Metadata'][0]['title']
        self.Guid = self.data['MediaContainer']['Metadata'][0]['Guid']
        self._Role = self.data['MediaContainer']['Metadata'][0]['Role']
        self.type = self.data['MediaContainer']['Metadata'][0]['type']
        self.librarySectionID = self.data['MediaContainer']['librarySectionID']

    def roles(self):
        roles = []
        for role in self._Role:
            roles.append(Role(role,self._server,self.librarySectionID))
        return roles
       
class Role():
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

def check_chs(name):
    for ch in name:
        if '\u4e00' <= ch <= '\u9fff' or ch == ' ' or ch == '·':
            continue
        else:
            return False
    return True

def formatchs(name):
    chs = ''
    for ch in name:
        if '\u4e00' <= ch <= '\u9fff':
            chs += ch
        elif ch.isalnum():
            chs += f'{ch}-'
        elif ch == '-':
            pass
        else:
            chs += '-'
    return chs

async def request_mydb(session,cid):
    url = 'https://api.lolic.cc/v1/people/idsearch'
    para ={'id': cid}
    while True:
        try:
            async with session.get(url,params=para) as res:
                data = await res.json()
                break
        except:
            log.error('连接失败，正在重试...')
            await asyncio.sleep(1)
    return data

async def io_task(media,session,tasks,sem):
    try:
        async with sem:
            video = await media.fetchitem(media.ratingKey)
            for guid in video.Guid:
                A = True
                if 'tmdb' in guid.get('id').lower():
                    A = False
                    r = re.findall(r'\d+',guid.get('id'),re.S)[0]
                    break
            if A:
                log.warning(video.title+' don"t have tmdb_id')
            else:
                if video.type == 'show':
                    url = f'https://api.themoviedb.org/3/tv/{r}/aggregate_credits?api_key={TMDB_API_KEY}&language=zh-CN'
                elif video.type == 'movie':
                    url = f'https://api.themoviedb.org/3/movie/{r}/credits?api_key={TMDB_API_KEY}&language=zh-CN'
                else:
                    log.warning('只支持电影和剧集')
                    tasks.remove(asyncio.current_task())
                    return
                try:
                    if ISPROXY:
                        async with session.get(url,proxy=PROXY) as res:
                            if res.status == 200:
                                tmdb_data = await res.json()
                    else:
                        async with session.get(url) as res:
                            if res.status == 200:
                                tmdb_data = await res.json()
                except:
                    log.error('连接失败，正在重试...')
                    await asyncio.sleep(1)
                cast_dir = {}
                for cast in tmdb_data['cast']:
                    if cast['known_for_department'] == 'Acting':
                        cast_dir[f'{cast["name"]}'] = cast['id']
                roles = video.roles()
                actor = []
                for role in roles:
                    if not check_chs(role.tag):
                        if cast_dir.get(role.tag,None):
                            cid = cast_dir.get(role.tag)
                            chsdir = await request_mydb(session,cid)
                            if chsdir['chs']:
                                chsname = chsdir['chs']
                                log.info(f'{video.title}: {role.tag} ------> {chsname}')
                                role.tag = chsname
                                actor.append(role)
                            else:
                                log.info(f'{video.title}: {role.tag} don"t have chinese name')
                                actor.append(role)
                        else:
                            log.warning(f'{video.title}: don"t find the cast({role.tag}) in tmdb')
                            actor.append(role)
                    else:
                        log.info(f'{video.title}: {role.tag} has the chinese name')
                        actor.append(role)
                await media.edit_role(actor)
                log.info(media.title+' has changed')
            tasks.remove(asyncio.current_task())
    except:
        log.critical(traceback.format_exc().splitlines()[-1])

async def sorttask(media,tasks,sem):
    try:
        async with sem:
            if media.titleSort is None:
                convert = pinyin(formatchs(media.title),style=Style(4))
                titlevalue = str.join('',list(map(lambda x:x[0],convert)))
                await media.edit_titlesort(titlevalue,lock=1)
                log.info(f'{media.title}: change titleSort into {titlevalue}')
            else:
                convert = pinyin(formatchs(media.title),style=Style(4))
                titlevalue = str.join('',list(map(lambda x:x[0],convert)))
                if titlevalue == media.titleSort:
                    log.info(f'{media.title}:alread {titlevalue}')
                else:
                    await media.edit_titlesort(titlevalue,lock=1)
                    log.info(f'{media.title}: change titleSort into {titlevalue}')
            tasks.remove(asyncio.current_task())
    except:
        log.critical(traceback.format_exc().splitlines()[-1])

async def main():
        sem = asyncio.Semaphore(CONCURRENT_NUM)
        plex = Plexserver(PLEX_URL,PLEX_TOKEN)
        library = await plex.library()
        sections = library.sections()
        tasks_role = []
        tasks_sort = []
        session = aiohttp.ClientSession()
        try:
            for section in sections:
                data = await section.all()
                for media in data:
                    task1 = asyncio.create_task(io_task(media=media,session=session,tasks=tasks_role,sem=sem))
                    task2 = asyncio.create_task(sorttask(media=media,tasks=tasks_sort,sem=sem))
                    tasks_role.append(task1)
                    tasks_sort.append(task2)

            for task in asyncio.as_completed(tasks_role):
                await task
            for task in asyncio.as_completed(tasks_sort):
                await task
            await session.close()
            await plex.close()
        except:
            log.critical(traceback.format_exc().splitlines()[-1])

            

if __name__ == '__main__':
    logfile = f'{datetime.now():%Y-%m-%d-%H-%M-%S}.log'

    log.add(os.path.join(LOG_PATH,logfile),
            enqueue=True,
            format='{time:YYYY-MM-DD HH:mm:ss} - {level} - {message}'
            )
    
    asyncio.run(main())