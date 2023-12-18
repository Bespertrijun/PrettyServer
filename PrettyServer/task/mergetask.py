import asyncio
import traceback
from server.embyserver import Embyserver
from server.embyserver import MixContent
from task.base import MergeTask as MT
from util.log import log
from util.exception import ServerTypeError

class MergeTask(MT):
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver,task_info)
        if not isinstance(self.server,Embyserver):
            raise ServerTypeError("合并任务只支持emby")

    async def _merge(self,ids,name):
        async with self.server.sem:
            try:
                log.info(f'{name}: 开始合并')
                await self.server.merge_version(ids)
                log.info(f'{name}: 合并完成，合并IDs:{ids}')
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            except:
                log.info(f'{name}合并失败: {traceback.format_exc()}')

    async def _emby_movie_merge(self,lb):
        try:
            mediaid = []
            #若为混合内容，则只获取电影类型媒体
            if isinstance(lb,MixContent):
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
            task = set()
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
                    future = asyncio.create_task(self._merge(ids,medias[v[0]].Name))
                    future.add_done_callback(task.discard)
                    task.add(future)
            await asyncio.gather(*task,return_exceptions=True)
            log.info(f"{lb.Name}：合并完成")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{lb.Name}合并失败： {traceback.format_exc()}')

    async def run(self):
        tasks = set()
        log.info(f"Emby({self.server.name})：开始合并版本任务，初始化中...")
        try:
            emby_library = await self.server.library()
            # 在emby媒体库中找出混合内容库和电影库
            for lb in emby_library:
                if lb.CollectionType in (None,"movies"):
                    future = asyncio.create_task(self._emby_movie_merge(lb))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)
                else:
                    log.info(f"{lb.Name}：非电影库或者混合内容，Emby合并版本任务跳过此库")
            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"Emby({self.server.name})：合并版本任务完毕")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(traceback.format_exc())