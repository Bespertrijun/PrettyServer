"""
全局变量模块
存放 API 和调度器共享的全局状态
"""
from typing import Optional, List
import asyncio
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 服务器列表
SERVERS: List = []

# TMDB 会话
TMDB_SESSION: Optional[aiohttp.ClientSession] = None

# 信号量（用于限制并发请求）
SEM: Optional[asyncio.Semaphore] = None

# APScheduler 调度器实例
SCHEDULER: Optional[AsyncIOScheduler] = None

# 同步任务实例字典 {任务名称: 任务对象}
SYNC_TASKS: dict = {}
