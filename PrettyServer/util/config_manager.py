"""
配置文件管理器
提供线程安全的配置读写功能，支持分块更新
"""
import yaml
import threading
import asyncio
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
from util.log import log
from util.crypto import crypto_manager


class ConfigManager:
    """配置文件管理器 - 单例模式"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            # 配置文件路径：优先使用 /data/config.yaml (Docker)，否则使用项目根目录
            data_config = Path('/data/config.yaml')
            if data_config.exists():
                self.config_path = data_config
            else:
                # 开发环境：使用项目根目录
                current_file = Path(__file__).resolve()
                project_root = current_file.parent.parent.parent
                self.config_path = project_root / 'config.yaml'

            # 读写锁
            self.file_lock = threading.Lock()

            # 缓存配置
            self._config_cache: Optional[Dict] = None

            # 运行时更新回调（用于同步 globalvar）
            self._on_server_deleted: Optional[Callable] = None
            self._on_server_added: Optional[Callable] = None
            self._on_server_updated: Optional[Callable] = None
            self._on_synctask_added: Optional[Callable] = None
            self._on_synctask_updated: Optional[Callable] = None
            self._on_synctask_deleted: Optional[Callable] = None
            self._on_env_updated: Optional[Callable] = None

            self.initialized = True

    def register_callbacks(
        self,
        on_server_deleted: Optional[Callable] = None,
        on_server_added: Optional[Callable] = None,
        on_server_updated: Optional[Callable] = None,
        on_synctask_added: Optional[Callable] = None,
        on_synctask_updated: Optional[Callable] = None,
        on_synctask_deleted: Optional[Callable] = None,
        on_env_updated: Optional[Callable] = None
    ):
        """注册配置变更回调函数（用于同步运行时状态）"""
        if on_server_deleted:
            self._on_server_deleted = on_server_deleted
        if on_server_added:
            self._on_server_added = on_server_added
        if on_server_updated:
            self._on_server_updated = on_server_updated
        if on_synctask_added:
            self._on_synctask_added = on_synctask_added
        if on_synctask_updated:
            self._on_synctask_updated = on_synctask_updated
        if on_synctask_deleted:
            self._on_synctask_deleted = on_synctask_deleted
        if on_env_updated:
            self._on_env_updated = on_env_updated

    async def _trigger_callback(self, callback: Optional[Callable], *args, **kwargs):
        """触发回调函数（统一处理同步/异步回调）

        Raises:
            Exception: 重新抛出回调中的异常，保留原始错误信息
        """
        if not callback:
            return True

        try:
            # 如果是异步回调，直接 await
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
                return True
            else:
                # 同步回调直接调用
                callback(*args, **kwargs)
                return True
        except Exception as e:
            from util.log import log
            log.error(f"回调执行失败: {e}")
            # 重新抛出原始异常，而不是返回 False
            raise

    def _read_config(self) -> Dict[str, Any]:
        """读取配置文件（带缓存）"""
        if self._config_cache is not None:
            return self._config_cache

        with self.file_lock:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.load(stream=f, Loader=yaml.FullLoader)
                self._config_cache = config
                return config

    def _write_config(self, config: Dict[str, Any]):
        """写入配置文件（原子操作）"""
        with self.file_lock:
            # 先写入临时文件
            temp_path = self.config_path.with_suffix('.yaml.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            # 原子替换
            temp_path.replace(self.config_path)

            # 清除缓存
            self._config_cache = None

    def reload_config(self):
        """重新加载配置（清除缓存）"""
        with self.file_lock:
            self._config_cache = None

    # ==================== Server 配置 ====================

    def get_servers(self) -> List[Dict[str, Any]]:
        """获取所有服务器配置"""
        config = self._read_config()
        return config.get('Server') or []

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取单个服务器配置"""
        servers = self.get_servers()
        log.debug(servers)
        for server in servers:
            if server.get('name') == name:
                return server
        return None

    async def update_server(self, name: str, server_data: Dict[str, Any]) -> bool:
        """更新指定服务器配置"""
        config = self._read_config()
        servers = config.get('Server') or []

        # 查找服务器
        for i, server in enumerate(servers):
            if server.get('name') == name:
                # 先触发运行时更新回调（失败会抛异常）
                await self._trigger_callback(self._on_server_updated, name, server_data)

                # 回调成功后写入配置，加密密码
                server_to_save = server_data.copy()

                # 处理密码：如果有新密码则加密，如果没有则保留原密码
                if server_to_save.get('password'):
                    server_to_save['password'] = crypto_manager.encrypt_password(server_to_save['password'])
                elif 'password' not in server_to_save and server.get('password'):
                    server_to_save['password'] = server.get('password')

                # 处理用户名：如果没有则保留原用户名
                if 'username' not in server_to_save and server.get('username'):
                    server_to_save['username'] = server.get('username')

                servers[i] = server_to_save
                config['Server'] = servers
                self._write_config(config)

                return True

        return False

    async def add_server(self, server_data: Dict[str, Any]):
        """添加新服务器（先触发运行时更新，成功后再写入配置）"""
        # 先触发运行时更新回调（失败会抛异常）
        await self._trigger_callback(self._on_server_added, server_data.get('name'), server_data)

        # 回调成功后写入配置，加密密码
        config = self._read_config()
        servers = config.get('Server') or []

        # 复制数据并加密密码
        server_to_save = server_data.copy()
        if server_to_save.get('password'):
            server_to_save['password'] = crypto_manager.encrypt_password(server_to_save['password'])

        servers.append(server_to_save)
        config['Server'] = servers
        self._write_config(config)

    async def delete_server(self, name: str) -> bool:
        """删除指定服务器（先触发运行时更新，成功后再写入配置）"""
        config = self._read_config()
        servers = config.get('Server') or []

        # 检查服务器是否存在
        if not any(s.get('name') == name for s in servers):
            return False

        # 先触发运行时更新回调（失败会抛异常）
        await self._trigger_callback(self._on_server_deleted, name)

        # 回调成功后再写入配置
        new_servers = [s for s in servers if s.get('name') != name]
        config['Server'] = new_servers
        self._write_config(config)

        return True

    # ==================== Synctask 配置 ====================

    def get_synctasks(self) -> List[Dict[str, Any]]:
        """获取所有同步任务配置"""
        config = self._read_config()
        return config.get('Synctask') or []

    def get_synctask_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取单个同步任务配置"""
        tasks = self.get_synctasks()
        for task in tasks:
            if task.get('name') == name:
                return task
        return None

    async def update_synctask(self, name: str, task_data: Dict[str, Any]) -> bool:
        """更新指定同步任务配置（先触发运行时更新，成功后再写入配置）"""
        config = self._read_config()
        tasks = config.get('Synctask') or []

        for i, task in enumerate(tasks):
            if task.get('name') == name:
                # 先触发运行时更新回调（传入原始数据，包含 isfirst=true，失败会抛异常）
                await self._trigger_callback(self._on_synctask_updated, name, task_data)

                # 回调成功后写入配置，如果 isfirst 为 true，写入时改为 false
                task_to_save = task_data.copy()
                if task_to_save.get('isfirst', False):
                    task_to_save['isfirst'] = False

                tasks[i] = task_to_save
                config['Synctask'] = tasks
                self._write_config(config)

                return True

        return False

    async def add_synctask(self, task_data: Dict[str, Any]):
        """添加新同步任务（先触发运行时更新，成功后再写入配置）"""
        # 先触发运行时更新回调（传入原始数据，包含 isfirst=true，失败会抛异常）
        await self._trigger_callback(self._on_synctask_added, task_data.get('name'), task_data)

        # 回调成功后写入配置，如果 isfirst 为 true，写入时改为 false
        config = self._read_config()
        tasks = config.get('Synctask') or []

        # 复制 task_data 避免修改原始数据
        task_to_save = task_data.copy()
        if task_to_save.get('isfirst', False):
            task_to_save['isfirst'] = False

        tasks.append(task_to_save)
        config['Synctask'] = tasks
        self._write_config(config)

    async def delete_synctask(self, name: str) -> bool:
        """删除指定同步任务（先触发运行时更新，成功后再写入配置）"""
        config = self._read_config()
        tasks = config.get('Synctask') or []

        # 检查任务是否存在
        if not any(t.get('name') == name for t in tasks):
            return False

        # 先触发运行时更新回调（失败会抛异常）
        await self._trigger_callback(self._on_synctask_deleted, name)

        # 回调成功后再写入配置
        new_tasks = [t for t in tasks if t.get('name') != name]
        config['Synctask'] = new_tasks
        self._write_config(config)

        return True

    # ==================== CollectionSyncTask 配置 ====================

    def get_collection_synctasks(self) -> List[Dict[str, Any]]:
        """获取所有合集同步任务配置"""
        config = self._read_config()
        return config.get('CollectionSyncTask') or []

    def update_collection_synctask(self, name: str, task_data: Dict[str, Any]) -> bool:
        """更新指定合集同步任务配置"""
        config = self._read_config()
        tasks = config.get('CollectionSyncTask') or []

        for i, task in enumerate(tasks):
            if task.get('name') == name:
                tasks[i] = task_data
                config['CollectionSyncTask'] = tasks
                self._write_config(config)
                return True

        return False

    def add_collection_synctask(self, task_data: Dict[str, Any]):
        """添加新合集同步任务"""
        config = self._read_config()
        tasks = config.get('CollectionSyncTask') or []
        tasks.append(task_data)
        config['CollectionSyncTask'] = tasks
        self._write_config(config)

    def delete_collection_synctask(self, name: str) -> bool:
        """删除指定合集同步任务"""
        config = self._read_config()
        tasks = config.get('CollectionSyncTask') or []

        new_tasks = [t for t in tasks if t.get('name') != name]

        if len(new_tasks) < len(tasks):
            config['CollectionSyncTask'] = new_tasks
            self._write_config(config)
            return True

        return False

    # ==================== Env 配置 ====================

    def get_env(self) -> Dict[str, Any]:
        """获取环境配置"""
        config = self._read_config()
        return config.get('Env', {})

    async def update_env(self, env_data: Dict[str, Any]):
        """更新环境配置（先触发运行时更新，成功后再写入配置）"""
        # 先触发运行时更新回调（失败会抛异常）
        await self._trigger_callback(self._on_env_updated, env_data)

        # 回调成功后再写入配置
        config = self._read_config()
        config['Env'] = env_data
        self._write_config(config)


# 全局单例实例
CM = ConfigManager()
