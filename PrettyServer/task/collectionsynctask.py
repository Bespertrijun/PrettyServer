import asyncio
import traceback
from asyncio import Lock
from server.embyserver import Embyserver
from server.jellyfinserver import Jellyfinserver
from server.plexserver import Plexserver
from conf.conf import check_exist
from util.log import log
from util.exception import ServerTypeError

class CollectionSyncTask:
    """
    合集同步任务类
    支持在Plex、Emby、Jellyfin服务器之间同步合集信息
    支持的同步组合:
    1. Emby <-> Jellyfin (同一套API逻辑)
    2. Plex <-> Emby (不同API逻辑)
    3. Plex <-> Jellyfin (不同API逻辑)
    """
    def __init__(self, task_info: dict, servers) -> None:
        self._info = task_info
        self.name = check_exist(self._info, "name", 'CollectionSyncTask')
        self.is_run = check_exist(self._info, "run", 'CollectionSyncTask')
        self.crontab = check_exist(self._info, "crontab", self.name)
        self._loadinfo()
        self.lock = Lock()
        self.server1 = None
        self.server2 = None
        
        # 查找指定的两个服务器 (支持Plex, Emby, Jellyfin)
        for server in servers:
            if server.name in self.which and isinstance(server, (Plexserver, Embyserver, Jellyfinserver)):
                if self.server1 is None:
                    self.server1 = server
                elif self.server2 is None:
                    self.server2 = server
                    
        if self.server1 is None or self.server2 is None:
            raise ServerTypeError(f"{self.name}: 需要指定两个有效的Plex/Emby/Jellyfin服务器")
        
        # 确定同步类型
        self.sync_type = self._determine_sync_type()
    
    def _loadinfo(self):
        """加载配置信息"""
        self.which = check_exist(self._info, "which", self.name)
        self.library_pairs = check_exist(self._info, "library_pairs", self.name)
    
    def _determine_sync_type(self):
        """确定同步类型"""
        server1_type = self.server1.type
        server2_type = self.server2.type
        
        if server1_type == "plex" or server2_type == "plex":
            # Emby/Jellyfin之间的同步
            return "no_plex"
        else :
            # Plex -> Emby/Jellyfin的同步
            return "has_plex"
        
    async def _get_collections_from_library(self, server, library_id):
        """从指定库获取所有合集"""
        try:
            librarie = await server.get_library_by_id(library_name)
            target_library = None
            
            # 查找指定的库
            for lib in libraries:
                if lib.Name == library_name:
                    target_library = lib
                    break
                    
            if target_library is None:
                log.warning(f"{server.type.title()}({server.name}): 未找到库 '{library_name}'")
                return []
                
            # TODO: 这里需要实现获取合集的API调用
            # 您可以在这里添加具体的API调用代码
            collections = await self._fetch_collections_from_api(server, target_library)
            
            log.info(f"{server.type.title()}({server.name}): 从库 '{library_name}' 获取到 {len(collections)} 个合集")
            return collections
            
        except Exception as e:
            log.error(f"{server.type.title()}({server.name}): 获取库 '{library_name}' 的合集失败: {str(e)}")
            return []
    
    async def _fetch_collections_from_api(self, server, library):
        """
        从API获取合集信息
        根据同步类型调用不同的API逻辑
        TODO: 这里需要您实现具体的API调用逻辑
        """
        collections = []
        
        if self.sync_type == "emby_jellyfin":
            # Emby/Jellyfin API调用
            # 示例API调用结构（需要您具体实现）:
            # url = f"{server.url}/Collections"
            # params = {
            #     "ParentId": library.Id,
            #     "api_key": server.token
            # }
            # async with server.session.get(url, params=params) as response:
            #     data = await response.json()
            #     collections = data.get("Items", [])
            log.info(f"TODO: 实现从 {server.type.title()}({server.name}) 获取合集的API调用 (Emby/Jellyfin模式)")
            
        elif self.sync_type == "plex_to_emby_jellyfin":
            # Plex <-> Emby/Jellyfin 混合API调用
            if server == self.server1:  # Plex服务器
                # 示例Plex API调用结构（需要您具体实现）:
                # url = f"{server.url}/library/sections/{library.key}/collections"
                # headers = {"X-Plex-Token": server.token}
                # async with server.session.get(url, headers=headers) as response:
                #     data = await response.xml()  # Plex返回XML
                #     collections = self._parse_plex_collections(data)
                log.info(f"TODO: 实现从 Plex({server.name}) 获取合集的API调用")
            else:  # Emby/Jellyfin服务器
                # 使用Emby/Jellyfin API
                log.info(f"TODO: 实现从 {server.type.title()}({server.name}) 获取合集的API调用")
        
        return collections
    
    async def _sync_collection(self, collection1, collection2, server1, server2):
        """合集并集同步 - 将两个服务器的合集内容合并"""
        try:
            async with self.lock:
                collection1_name = collection1.get("Name", "未知合集") if collection1 else None
                collection2_name = collection2.get("Name", "未知合集") if collection2 else None
                
                # 如果只有一方有合集，直接同步
                if collection1 and not collection2:
                    log.info(f"合集 '{collection1_name}' 只存在于 {server1.type.title()}({server1.name})，开始同步到 {server2.type.title()}({server2.name})")
                    await self._sync_collection_from_source_to_target(collection1, server1, server2)
                    return
                    
                elif collection2 and not collection1:
                    log.info(f"合集 '{collection2_name}' 只存在于 {server2.type.title()}({server2.name})，开始同步到 {server1.type.title()}({server1.name})")
                    await self._sync_collection_from_source_to_target(collection2, server2, server1)
                    return
                
                # 如果两边都有合集，执行并集同步
                elif collection1 and collection2:
                    log.info(f"开始执行合集并集同步: '{collection1_name}' <-> '{collection2_name}'")
                    await self._sync_collections_union(collection1, collection2, server1, server2)
                
        except Exception as e:
            log.error(f"合集同步失败: {str(e)}")
            log.error(traceback.format_exc())
    
    async def _sync_collections_union(self, collection1, collection2, server1, server2):
        """执行两个合集的并集同步"""
        try:
            # 获取两个合集的媒体项目
            items1 = collection1.get("MediaItems", [])
            items2 = collection2.get("MediaItems", [])
            
            log.info(f"合集1({server1.name}): {len(items1)}项, 合集2({server2.name}): {len(items2)}项")
            
            # 找出需要同步的项目
            items_to_add_to_server2 = await self._find_missing_items(items1, items2, server1, server2)
            items_to_add_to_server1 = await self._find_missing_items(items2, items1, server2, server1)
            
            sync_tasks = []
            
            # 向服务器2添加缺失的项目
            if items_to_add_to_server2:
                log.info(f"向 {server2.type.title()}({server2.name}) 的合集添加 {len(items_to_add_to_server2)} 个项目")
                sync_tasks.append(
                    self._add_items_to_collection(collection2, items_to_add_to_server2, server2)
                )
            
            # 向服务器1添加缺失的项目  
            if items_to_add_to_server1:
                log.info(f"向 {server1.type.title()}({server1.name}) 的合集添加 {len(items_to_add_to_server1)} 个项目")
                sync_tasks.append(
                    self._add_items_to_collection(collection1, items_to_add_to_server1, server1)
                )
            
            # 并行执行同步任务
            if sync_tasks:
                await asyncio.gather(*sync_tasks, return_exceptions=True)
                log.info(f"合集 '{collection1.get('Name')}' 并集同步完成")
            else:
                log.info(f"合集 '{collection1.get('Name')}' 内容已同步，无需更新")
                
        except Exception as e:
            log.error(f"合集并集同步失败: {str(e)}")
    
    async def _find_missing_items(self, source_items, target_items, source_server, target_server):
        """找出目标合集中缺失的媒体项目"""
        missing_items = []
        
        # 创建目标项目的匹配索引（使用多种匹配方式）
        target_index = self._create_media_index(target_items)
        
        for source_item in source_items:
            if not self._is_item_in_target(source_item, target_index, source_server, target_server):
                # 尝试在目标服务器中找到对应的媒体项目
                matched_item = await self._find_matching_media_in_server(source_item, source_server, target_server)
                if matched_item:
                    missing_items.append(matched_item)
                    
        return missing_items
    
    def _create_media_index(self, items):
        """为媒体项目创建多种匹配索引"""
        index = {
            'names': set(),
            'provider_ids': {},
            'paths': set()
        }
        
        for item in items:
            # 名称索引
            if item.get('Name'):
                index['names'].add(item['Name'].lower())
            
            # Provider ID索引
            provider_ids = item.get('ProviderIds', {})
            for provider, pid in provider_ids.items():
                if provider not in index['provider_ids']:
                    index['provider_ids'][provider] = set()
                index['provider_ids'][provider].add(pid)
            
            # 路径索引（文件名部分）
            if item.get('Path'):
                import os
                filename = os.path.basename(item['Path']).lower()
                index['paths'].add(filename)
                
        return index
    
    def _is_item_in_target(self, source_item, target_index, source_server, target_server):
        """检查源项目是否已存在于目标合集中"""
        # 1. 通过名称匹配
        if source_item.get('Name') and source_item['Name'].lower() in target_index['names']:
            return True
        
        # 2. 通过Provider ID匹配
        source_provider_ids = source_item.get('ProviderIds', {})
        for provider, pid in source_provider_ids.items():
            if (provider in target_index['provider_ids'] and 
                pid in target_index['provider_ids'][provider]):
                return True
        
        # 3. 通过文件名匹配
        if source_item.get('Path'):
            import os
            source_filename = os.path.basename(source_item['Path']).lower()
            if source_filename in target_index['paths']:
                return True
                
        return False
    
    async def _find_matching_media_in_server(self, source_item, source_server, target_server):
        """在目标服务器中查找与源项目匹配的媒体"""
        try:
            source_name = source_item.get('Name', '未知媒体')
            log.debug(f"查找媒体项目 '{source_name}' 在 {target_server.type.title()}({target_server.name}) 中的匹配")
            
            # 获取源项目的Provider IDs
            source_provider_ids = source_item.get('ProviderIds', {})
            if not source_provider_ids:
                log.debug(f"源媒体 '{source_name}' 没有Provider ID，跳过搜索")
                return None
            
            # 使用Provider ID进行搜索
            search_results = []
            
            # 尝试使用不同的Provider ID搜索
            for provider, provider_id in source_provider_ids.items():
                if not provider_id:
                    continue
                    
                # 根据不同的provider调用guidsearch
                kwargs = {}
                if provider.lower() == 'tmdb':
                    kwargs['tmdb'] = provider_id
                elif provider.lower() == 'imdb':
                    kwargs['imdb'] = provider_id  
                elif provider.lower() == 'tvdb':
                    kwargs['tvdb'] = provider_id
                else:
                    continue  # 不支持的Provider类型
                
                try:
                    # 使用guidsearch在目标服务器中搜索
                    results = await target_server.guidsearch(**kwargs)
                    if results:
                        search_results.extend(results)
                        log.debug(f"通过 {provider}:{provider_id} 找到 {len(results)} 个匹配项")
                        break  # 找到匹配项就停止搜索
                except Exception as e:
                    log.warning(f"使用 {provider}:{provider_id} 搜索失败: {str(e)}")
                    continue
            
            if not search_results:
                log.debug(f"在 {target_server.type.title()}({target_server.name}) 中未找到媒体 '{source_name}' 的匹配项")
                return None
            
            # 如果找到多个结果，优先返回第一个匹配项
            # TODO: 这里可以进一步优化，根据库ID或其他条件过滤结果
            matched_media = search_results[0]
            
            # 构造返回的媒体对象（根据服务器类型处理不同的属性结构）
            if target_server.type == "plex":
                # Plex 使用 ratingKey 而不是 Id，title 而不是 Name
                result = {
                    'Id': getattr(matched_media, 'ratingKey', None),  # Plex 使用 ratingKey
                    'Name': getattr(matched_media, 'title', None),    # Plex 使用 title
                    'Type': getattr(matched_media, 'type', None),     # 类型字段一致
                    'ProviderIds': {}  # Plex 的 Provider IDs 需要通过 fetchitem() 获取
                }
            else:
                # Emby/Jellyfin 使用标准字段
                result = {
                    'Id': getattr(matched_media, 'Id', None),
                    'Name': getattr(matched_media, 'Name', None),
                    'Type': getattr(matched_media, 'Type', None),
                    'ProviderIds': getattr(matched_media, 'data', {}).get('ProviderIds', {}) if hasattr(matched_media, 'data') else {}
                }
            
            log.debug(f"在 {target_server.type.title()}({target_server.name}) 中找到匹配媒体: {result.get('Name')}")
            return result
            
        except Exception as e:
            log.error(f"搜索匹配媒体时发生错误: {str(e)}")
            return None
    
    async def _add_items_to_collection(self, collection, items, server):
        """向合集添加媒体项目"""
        # TODO: 实现向合集添加项目的API调用
        collection_name = collection.get('Name', '未知合集')
        log.info(f"向 {server.type.title()}({server.name}) 的合集 '{collection_name}' 添加 {len(items)} 个项目")
        
        # 这里需要调用相应的API来添加项目到合集
        # Emby/Jellyfin: POST /Collections/{id}/Items
        # Plex: PUT /library/collections/{id}/items
    
    async def _sync_collection_from_source_to_target(self, source_collection, source_server, target_server):
        """从源服务器同步整个合集到目标服务器"""
        try:
            collection_name = source_collection.get('Name')
            log.info(f"开始创建合集 '{collection_name}' 到 {target_server.type.title()}({target_server.name})")
            
            # TODO: 实现创建新合集和添加所有项目的逻辑
            # 1. 在目标服务器创建合集
            # 2. 为源合集中的每个项目在目标服务器中找到对应项目
            # 3. 将找到的项目添加到新创建的合集中
            
            log.info(f"合集 '{collection_name}' 同步完成")
            
        except Exception as e:
            log.error(f"合集同步失败: {str(e)}")
    
    async def _match_collections(self, collections1, collections2):
        """匹配两个服务器中的合集"""
        matches = []
        
        # 简单的名称匹配逻辑（您可以根据需要改进）
        for col1 in collections1:
            col1_name = col1.get("Name", "")
            for col2 in collections2:
                col2_name = col2.get("Name", "")
                if col1_name == col2_name:
                    matches.append((col1, col2))
                    break
                
                    
        log.info(f"匹配到 {len(matches)} 个相同名称的合集")
        return matches
    
    async def _sync_library_pair_collections(self, library1_name, library2_name):
        """同步指定库对的合集"""
        try:
            log.info(f"开始同步库对: '{library1_name}' ({self.server1.type.title()}) <-> '{library2_name}' ({self.server2.type.title()})")
            
            # 获取两个服务器中指定库的合集
            collections1 = await self._get_collections_from_library(self.server1, library1_name)
            collections2 = await self._get_collections_from_library(self.server2, library2_name)
            
            if not collections1 and not collections2:
                log.warning(f"库对 '{library1_name}' <-> '{library2_name}' 在两个服务器中都没有合集")
                return
                
            # 匹配合集
            matched_collections = await self._match_collections(collections1, collections2)
            
            # 同步匹配的合集
            tasks = []
            for col1, col2 in matched_collections:
                task = asyncio.create_task(
                    self._sync_collection(col1, col2, self.server1, self.server2)
                )
                tasks.append(task)
                
            # 处理只在一个服务器中存在的合集
            unmatched_collections1 = [col for col in collections1 
                                    if not any(col.get('Name') == matched[0].get('Name') 
                                             for matched in matched_collections)]
            unmatched_collections2 = [col for col in collections2 
                                    if not any(col.get('Name') == matched[1].get('Name') 
                                             for matched in matched_collections)]
            
            # 同步单边合集
            for col in unmatched_collections1:
                task = asyncio.create_task(
                    self._sync_collection(col, None, self.server1, self.server2)
                )
                tasks.append(task)
                
            for col in unmatched_collections2:
                task = asyncio.create_task(
                    self._sync_collection(None, col, self.server1, self.server2)
                )
                tasks.append(task)
                
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
            log.info(f"库对 '{library1_name}' <-> '{library2_name}' 合集同步完成")
            
        except Exception as e:
            log.error(f"库对 '{library1_name}' <-> '{library2_name}' 合集同步失败: {str(e)}")
    
    # 入口
    async def run(self):
        """执行合集同步任务"""
        if not self.is_run:
            return
            
        try:
            server1_name = f"{self.server1.type.title()}({self.server1.name})"
            server2_name = f"{self.server2.type.title()}({self.server2.name})"
            
            log.info(f"开始执行合集同步任务: {server1_name} <-> {server2_name}")
            
            # 对每个库对执行同步
            for library_pair in self.library_pairs:
                if len(library_pair) != 2:
                    log.warning(f"库对配置格式错误，跳过: {library_pair}")
                    continue
                    
                library1_name, library2_name = library_pair
                await self._sync_library_pair_collections(library1_name, library2_name)
                
            log.info(f"合集同步任务完成: {server1_name} <-> {server2_name}")
            
        except Exception as e:
            log.error(f"合集同步任务执行失败: {str(e)}")
            log.error(traceback.format_exc())