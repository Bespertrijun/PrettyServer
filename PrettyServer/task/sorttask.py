import asyncio
import traceback
from server.plexserver import Plexserver
from server.embyserver import Embyserver
from task.base import SortTask as ST
from util.log import log
from pypinyin import pinyin, Style,load_phrases_dict
#更新词典
load_phrases_dict({'九重天': [['j'], ['c'],['t']]})
load_phrases_dict({'神藏': [['s'], ['z']]})

class SortTask(ST):
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver, task_info)

    async def _plexsort(self,media):
        async with self.server.sem:
            try:
                await media.fetchitem()
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
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            except:
                log.error(f'{media.title}修改标题失败：{traceback.format_exc()}')

    async def _embysort(self,media):
        async with self.server.sem:
            try:
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
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            except:
                log.critical(f'{media.Name}标题排序失败：{traceback.format_exc()}')   

    async def run(self):
        log.info(f"{self.server.type.capitalize()}({self.server.name})：开始进行标题排序，拼音搜索...")
        try:
            tasks = set()
            if isinstance(self.server,Plexserver):
                library = await self.server.library()
                sections = library.sections()
            elif isinstance(self.server,Embyserver):
                sections = await self.server.library()
            for lb in sections:
                if isinstance(self.server,Embyserver):
                    if lb.CollectionType not in (None,"movies","tvshows"):
                        log.warning(f'{lb.Name}：只支持电影、剧集和混合内容库，跳过此库')
                        continue
                data = await lb.all()
                for media in data:
                    if isinstance(self.server,Embyserver):
                        future = asyncio.create_task(self._embysort(media=media))
                    elif isinstance(self.server,Plexserver):
                        future = asyncio.create_task(self._plexsort(media=media))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"{self.server.type.capitalize()}({self.server.name})：标题排序，拼音搜索任务执行完毕")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{self.server.type.capitalize()}({self.server.name})演员中文化执行失败：{traceback.format_exc()}')