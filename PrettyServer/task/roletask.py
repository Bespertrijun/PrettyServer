import asyncio
import traceback
from task.base import RoleTask
from util.log import log

class EmbyRoleTask(RoleTask):
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver, task_info)

    async def _emby_role(self,p):
        try:
            if p.check_chs(p.Name):
                log.info(f'{p.Name}：已有中文信息')
                return
            if p.ProviderIds:
                if p.tmdbid:
                    data = await self.server.get_chs_name(p.tmdbid)
                    if data['chs']:
                        await p.fetchitem()
                        p.data["Name"] = data['chs']
                        await p.edit(p.data)
                        log.info(f'{p.Name}：修改为{data["chs"]}')
                    else:
                        log.info(f'{p.Name}：tmdb没有中文信息')
                else:
                    log.warning(f'{p.Name}：没有Tmdbid信息')
            else:
                log.warning(f'{p.Name}：没有ProviderIds信息')
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'{p.Name}修改中文名失败：{traceback.format_exc()}')

    async def run(self):
        log.info(f"{self.server.type.title()}({self.server.name})：开始进行演员中文化...")
        try:
            tasks = set()
            async for p in self.server.get_person():
                future = asyncio.create_task(self._emby_role(p))
                future.add_done_callback(tasks.discard)
                tasks.add(future)
            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"{self.server.type.title()}({self.server.name})：演员中文化执行完毕")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(traceback.format_exc())
        finally:
            # 清空缓存，释放内存
            from util.util import Util
            Util.clear_role_cache()
            log.info(f"{self.server.type.title()}({self.server.name})：已清空演员数据缓存")

class PlexRoleTask(RoleTask):
    def __init__(self, mediaserver, task_info: dict) -> None:
        super().__init__(mediaserver, task_info)

    async def _plexrole(self,media):
        async with self.server.sem:
            try:
                await media.fetchitem()
                if not media.tmdbid:
                    log.warning(media.title+': 未找到该条目tmdb ID')
                    return
                if media.type == 'show':
                    type = "tv"
                elif media.type == 'movie':
                    type = 'movie'
                else:
                    log.warning('Plex只支持电影和剧集')
                    return
                tmdb_data = await media.get_role_from_id(type,media.tmdbid)
                cast_dir = {}
                for cast in tmdb_data['cast']:
                    if cast['known_for_department'] == 'Acting':
                        cast_dir[f'{cast["name"]}'] = cast['id']
                roles = media.roles()
                actor = []
                for role in roles:
                    if not role.check_chs(role.tag):
                        if cast_dir.get(role.tag,None):
                            cid = cast_dir.get(role.tag)
                            chsdir = await role.get_chs_name(cid)
                            if chsdir['chs']:
                                chsname = chsdir['chs']
                                log.info(f'{media.title}: {role.tag} ------> {chsname}')
                                role.tag = chsname
                                actor.append(role)
                            else:
                                log.info(f'{media.title}: {role.tag} 暂无中文数据')
                                actor.append(role)
                        else:
                            log.warning(f'{media.title}: {role.tag} 未发现该演员在该影视tmdb条目中')
                            actor.append(role)
                    else:
                        log.info(f'{media.title}: {role.tag} 此演员已有中文数据')
                        actor.append(role)
                await media.edit_role(actor)
                log.info(media.title+': 修改完毕')
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            except:
                log.error(f'{media.title}修改演员失败：{traceback.format_exc()}')

    async def run(self):
        log.info(f"Plex({self.server.name})：开始进行演员中文化...")
        try:
            tasks = set()
            library = await self.server.library()
            sections = library.sections()
            for section in sections:
                data = await section.all()
                for media in data:
                    future = asyncio.create_task(self._plexrole(media=media))
                    future.add_done_callback(tasks.discard)
                    tasks.add(future)

            await asyncio.gather(*tasks,return_exceptions=True)
            log.info(f"Plex({self.server.name})：演员中文化执行完毕")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except:
            log.critical(f'Plex({self.server.name})演员中文化执行失败：{traceback.format_exc()}')
        finally:
            # 清空缓存，释放内存
            from util.util import Util
            Util.clear_role_cache()
            log.info(f"Plex({self.server.name})：已清空演员数据缓存")