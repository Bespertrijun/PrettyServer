from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette_session import SessionMiddleware
import os
import sys
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum
import secrets
import bcrypt
import pyotp
import qrcode
import io
import base64

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util.log import log
import util.globalvar as g
from util.config_manager import CM
from util.crypto import crypto_manager

# 配置常量
SERVER_CONNECTION_TIMEOUT = 5.0  # 服务器连接测试超时时间（秒）

app = FastAPI(title="PrettyServer API", version="1.0.0", description="媒体服务器管理工具 API")

# 配置 Session 中间件
SECRET_KEY = secrets.token_urlsafe(32)  # 生成随机密钥
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    cookie_name="prettyserver_session",
    same_site="lax",
    max_age=7 * 24 * 60 * 60,  # 7天
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 系统状态枚举（移到前面以避免前向引用问题）
class SystemStatusEnum(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    INITIALIZING = "initializing"

# 辅助函数
def get_servers_count() -> int:
    """动态获取服务器数量"""
    return len(g.SERVERS)

def get_active_tasks_count() -> int:
    """通过 APScheduler 获取活跃任务数量"""
    if g.SCHEDULER is None:
        return 0
    try:
        jobs = g.SCHEDULER.get_jobs()
        return len(jobs)
    except Exception as e:
        log.error(f"获取任务数量失败: {e}")
        return 0

async def get_system_status_and_failed_count() -> tuple[SystemStatusEnum, int]:
    """根据系统状态判断健康度，返回 (状态, 失败服务器数量)"""
    # 调度器未初始化
    if g.SCHEDULER is None:
        return SystemStatusEnum.INITIALIZING, 0

    # 没有配置服务器，系统正常运行
    if not g.SERVERS:
        return SystemStatusEnum.HEALTHY, 0

    # 检查是否有服务器连接失败
    failed_servers = 0
    for server in g.SERVERS:
        is_connected = await server.test_connection(timeout=SERVER_CONNECTION_TIMEOUT)
        if not is_connected:
            failed_servers += 1

    # 判断状态
    if failed_servers == 0:
        status = SystemStatusEnum.HEALTHY
    elif failed_servers < len(g.SERVERS):
        status = SystemStatusEnum.DEGRADED
    else:
        status = SystemStatusEnum.ERROR

    return status, failed_servers

# 数据模型
class ServerInfo(BaseModel):
    name: str
    type: str
    url: str
    status: str  # connected / disconnected

class TaskConfig(BaseModel):
    run: bool
    crontab: str

class ServerConfig(BaseModel):
    name: str
    type: str
    url: str
    token: str
    username: Optional[str] = None
    password: Optional[str] = None
    roletask: Optional[TaskConfig] = None
    sorttask: Optional[TaskConfig] = None
    scantask: Optional[Dict] = None
    mergetask: Optional[TaskConfig] = None
    titletask: Optional[TaskConfig] = None

class SyncTaskConfig(BaseModel):
    name: str
    run: bool
    isfirst: bool
    which: List[str]

class SystemStatus(BaseModel):
    status: SystemStatusEnum
    servers_count: int
    failed_servers_count: int  # 连接失败的服务器数量
    active_tasks: int

# API 路由

@app.get("/api/status", response_model=SystemStatus)
async def get_system_status():
    """获取系统状态"""
    try:
        status, failed_count = await get_system_status_and_failed_count()
        return SystemStatus(
            status=status,
            servers_count=get_servers_count(),
            failed_servers_count=failed_count,
            active_tasks=get_active_tasks_count()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/crypto/public-key")
async def get_public_key():
    """获取加密公钥（用于前端加密密码）"""
    try:
        return {
            "public_key": crypto_manager.get_public_key_hex(),
            "algorithm": "ECC-secp256r1"
        }
    except Exception as e:
        log.error(f"获取公钥失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/servers", response_model=List[ServerInfo])
async def get_servers():
    """获取所有服务器列表"""
    try:
        server_list = []
        for server in g.SERVERS:
            # 测试服务器连接状态
            is_connected = await server.test_connection(timeout=SERVER_CONNECTION_TIMEOUT)
            server_info = ServerInfo(
                name=server.name,
                type=server.type,
                url=server.url,
                status="connected" if is_connected else "disconnected",
            )
            server_list.append(server_info)
        return server_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/servers/test")
async def test_server_connection(data: Dict[str, str]):
    """测试服务器连接

    Args:
        data: 包含 name 字段的字典

    Returns:
        连接测试结果
    """
    try:
        server_name = data.get('name')
        if not server_name:
            return {"status": "error", "message": "缺少服务器名称"}

        # 从全局服务器列表中查找服务器
        server = None
        for s in g.SERVERS:
            if s.name == server_name:
                server = s
                break

        if server is None:
            return {"status": "error", "message": f"服务器 '{server_name}' 不存在"}

        # 测试连接
        is_connected = await server.test_connection(timeout=SERVER_CONNECTION_TIMEOUT)

        if is_connected:
            return {"status": "success", "message": "连接成功"}
        else:
            return {"status": "error", "message": "连接失败"}

    except Exception as e:
        log.error(f"测试服务器连接失败: {e}")
        return {"status": "error", "message": f"连接测试异常: {str(e)}"}

@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """获取日志

    Args:
        lines: 返回最后 N 行日志，默认 100 行。如果日志不足 N 行，返回所有行
    """
    try:
        # 获取日志目录
        from conf.conf import LOG_PATH
        if LOG_PATH in ('default', None, '/log'):
            log_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        else:
            log_dir = LOG_PATH

        # 查找所有 .log 文件
        log_files = []
        if os.path.exists(log_dir):
            for filename in os.listdir(log_dir):
                if filename.endswith('.log'):
                    file_path = os.path.join(log_dir, filename)
                    log_files.append((file_path, os.path.getmtime(file_path)))

        if not log_files:
            return {"logs": []}

        # 获取最新的日志文件（按修改时间排序）
        latest_log_path = max(log_files, key=lambda x: x[1])[0]

        # 读取日志内容
        with open(latest_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_lines = f.readlines()
            # 返回最后 N 行（如果不足 N 行则返回全部），去除换行符
            return {"logs": [line.rstrip('\n') for line in log_lines[-lines:]]}

    except Exception as e:
        log.error(f"获取日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/servers/{server_name}/libraries")
async def get_server_libraries(server_name: str):
    """获取指定服务器的库列表"""
    try:
        # 从全局服务器列表中查找服务器
        server = None
        for s in g.SERVERS:
            if s.name == server_name:
                server = s
                break

        if server is None:
            raise HTTPException(status_code=404, detail=f"服务器 '{server_name}' 不存在")

        # 获取库列表
        libraries = []
        if server.type.lower() == 'plex':
            # Plex需要先获取library对象，再获取sections
            library_obj = await server.library()
            sections = library_obj.sections()
            for section in sections:
                libraries.append({
                    "name": section.title,
                    "id": section.key
                })
        else:
            # Emby/Jellyfin直接返回库列表
            library_list = await server.library()
            for lib in library_list:
                libraries.append({
                    "name": lib.Name,
                    "id": lib.Id
                })

        return {"libraries": libraries}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"获取服务器库列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的事件"""
    if g.TMDB_SESSION:
        await g.TMDB_SESSION.close()
    for server in g.SERVERS:
        if hasattr(server, 'close'):
            await server.close()

# ==================== 认证端点 ====================

# 获取当前登录用户的依赖
async def get_current_user(request: Request):
    """检查用户是否已登录"""
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user

@app.post("/api/auth/login")
async def login(request: Request, credentials: Dict[str, str]):
    """用户登录"""
    try:
        username = credentials.get('username')
        encrypted_password = credentials.get('password')

        if not username or not encrypted_password:
            raise HTTPException(status_code=400, detail="用户名和密码不能为空")

        # 解密密码
        try:
            password = crypto_manager.decrypt_password(encrypted_password)
        except Exception as e:
            log.error(f"密码解密失败: {e}")
            raise HTTPException(status_code=400, detail="密码格式错误")

        # 从配置中获取用户列表
        env_config = CM.get_env()
        users = env_config.get('users', [])

        # 查找匹配的用户
        user_found = None
        for user in users:
            if user.get('username') == username:
                # 使用 bcrypt 验证密码
                stored_password = user.get('password', '')
                if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                    user_found = user
                    break

        if not user_found:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 检查环境配置中是否启用了 2FA
        use_2fa = env_config.get('use_2fa', False)
        if use_2fa:
            # 检查用户是否已配置 2FA 密钥
            totp_secret = user_found.get('totp_secret')
            if not totp_secret:
                raise HTTPException(status_code=400, detail="系统已启用2FA，但您尚未配置。")

            # 需要 2FA 验证
            totp_code = credentials.get('totp_code')
            if not totp_code:
                # 密码正确但缺少 2FA 验证码，返回需要 2FA 的状态
                return {
                    "status": "require_2fa",
                    "message": "请输入2FA验证码",
                    "username": username
                }

            # 验证 2FA 验证码
            totp = pyotp.TOTP(totp_secret)
            if not totp.verify(totp_code, valid_window=1):
                raise HTTPException(status_code=401, detail="2FA验证码错误")

        # 设置 session
        request.session['user'] = username
        request.session['logged_in'] = True

        return {"status": "success", "message": "登录成功", "username": username}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"登录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/logout")
async def logout(request: Request):
    """用户登出"""
    try:
        request.session.clear()
        return {"status": "success", "message": "登出成功"}
    except Exception as e:
        log.error(f"登出失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/status")
async def auth_status(request: Request):
    """检查登录状态"""
    try:
        user = request.session.get('user')
        logged_in = request.session.get('logged_in', False)

        return {
            "logged_in": logged_in,
            "username": user if logged_in else None
        }
    except Exception as e:
        log.error(f"获取登录状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/changepassword")
async def change_password(request: Request, data: Dict[str, str], current_user: str = Depends(get_current_user)):
    """修改密码"""
    try:
        encrypted_old_password = data.get('old_password')
        encrypted_new_password = data.get('new_password')

        if not encrypted_old_password or not encrypted_new_password:
            raise HTTPException(status_code=400, detail="旧密码和新密码不能为空")

        # 解密密码
        try:
            old_password = crypto_manager.decrypt_password(encrypted_old_password)
            new_password = crypto_manager.decrypt_password(encrypted_new_password)
        except Exception as e:
            log.error(f"密码解密失败: {e}")
            raise HTTPException(status_code=400, detail="密码格式错误")

        # 从配置中获取用户列表
        env_config = CM.get_env()
        users = env_config.get('users', [])

        # 查找当前用户
        user_found = None
        user_index = -1
        for i, user in enumerate(users):
            if user.get('username') == current_user:
                user_found = user
                user_index = i
                break

        if not user_found:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 验证旧密码（使用 bcrypt）
        stored_password = user_found.get('password', '')
        if not bcrypt.checkpw(old_password.encode('utf-8'), stored_password.encode('utf-8')):
            raise HTTPException(status_code=401, detail="旧密码错误")

        # 使用 bcrypt 加密新密码
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        # 更新密码
        users[user_index]['password'] = hashed_password.decode('utf-8')
        env_config['users'] = users

        # 保存配置
        await CM.update_env(env_config)

        return {"status": "success", "message": "密码修改成功"}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"修改密码失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/2fa/enable")
async def enable_2fa(request: Request, current_user: str = Depends(get_current_user)):
    """启用2FA认证，返回密钥和二维码"""
    try:
        # 从配置中获取用户列表
        env_config = CM.get_env()
        users = env_config.get('users', [])

        # 查找当前用户
        user_found = None
        for user in users:
            if user.get('username') == current_user:
                user_found = user
                break

        if not user_found:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 生成新的 2FA 密钥
        secret = pyotp.random_base32()

        # 生成 TOTP URI（用于生成二维码）
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=current_user,
            issuer_name="PrettyServer"
        )

        # 生成二维码
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # 将二维码转换为 base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        # 临时保存到 session，等待验证
        request.session['pending_2fa_secret'] = secret

        return {
            "status": "success",
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_base64}",
            "message": "请使用认证器 APP 扫描二维码，然后输入验证码完成绑定"
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"启用 2FA 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/2fa/verify")
async def verify_2fa(request: Request, data: Dict[str, str], current_user: str = Depends(get_current_user)):
    """验证 2FA 验证码并完成绑定"""
    try:
        code = data.get('code')
        if not code:
            raise HTTPException(status_code=400, detail="验证码不能为空")

        # 从 session 获取待验证的密钥
        pending_secret = request.session.get('pending_2fa_secret')
        if not pending_secret:
            raise HTTPException(status_code=400, detail="请先启用 2FA")

        # 验证验证码
        totp = pyotp.TOTP(pending_secret)
        if not totp.verify(code, valid_window=1):
            raise HTTPException(status_code=401, detail="验证码错误")

        # 从配置中获取用户列表
        env_config = CM.get_env()
        users = env_config.get('users', [])

        # 查找当前用户并保存密钥
        user_index = -1
        for i, user in enumerate(users):
            if user.get('username') == current_user:
                user_index = i
                break

        if user_index == -1:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 保存 2FA 密钥
        users[user_index]['totp_secret'] = pending_secret
        env_config['users'] = users

        # 自动启用全局 2FA 开关
        env_config['use_2fa'] = True

        # 保存配置
        await CM.update_env(env_config)

        # 清除 session 中的临时密钥
        request.session.pop('pending_2fa_secret', None)

        return {"status": "success", "message": "双因素认证已启用"}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"验证 2FA 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/2fa/disable")
async def disable_2fa(request: Request, data: Dict[str, str], current_user: str = Depends(get_current_user)):
    """禁用双因素认证"""
    try:
        password = data.get('password')
        if not password:
            raise HTTPException(status_code=400, detail="请输入密码以确认操作")

        # 从配置中获取用户列表
        env_config = CM.get_env()
        users = env_config.get('users', [])

        # 查找当前用户
        user_index = -1
        user_found = None
        for i, user in enumerate(users):
            if user.get('username') == current_user:
                user_found = user
                user_index = i
                break

        if not user_found:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 验证密码
        stored_password = user_found.get('password', '')
        if not bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
            raise HTTPException(status_code=401, detail="密码错误")

        # 移除 2FA 密钥
        if 'totp_secret' in users[user_index]:
            users[user_index].pop('totp_secret')
            env_config['users'] = users

            # 同时关闭全局 2FA 开关（因为用户已经没有配置 2FA）
            env_config['use_2fa'] = False

            await CM.update_env(env_config)

        return {"status": "success", "message": "双因素认证已禁用"}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"禁用 2FA 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/2fa/status")
async def get_2fa_status(current_user: str = Depends(get_current_user)):
    """获取当前用户的 2FA 状态"""
    try:
        # 从配置中获取用户列表
        env_config = CM.get_env()
        users = env_config.get('users', [])

        # 查找当前用户
        for user in users:
            if user.get('username') == current_user:
                has_2fa = 'totp_secret' in user and user['totp_secret']
                return {
                    "enabled": has_2fa
                }

        raise HTTPException(status_code=404, detail="用户不存在")

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"获取 2FA 状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 配置管理端点 ====================

@app.get("/api/config/servers/{server_name}")
async def get_server_config(server_name: str):
    """获取单个服务器配置"""
    try:
        server = CM.get_server_by_name(server_name)
        if server is None:
            raise HTTPException(status_code=404, detail=f"服务器 {server_name} 不存在")

        # 移除密码字段，不返回给前端
        server_copy = server.copy()
        server_copy.pop('password', None)
        return server_copy
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"获取服务器配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/config/servers/{server_name}")
async def update_server_config(server_name: str, server_data: Dict[str, Any]):
    """更新服务器配置"""
    try:
        new_name = server_data.get('name')

        # 检查原服务器是否存在
        if not CM.get_server_by_name(server_name):
            raise HTTPException(status_code=404, detail=f"服务器 {server_name} 不存在")

        # 如果改名，检查新名称是否已存在
        if new_name != server_name:
            if CM.get_server_by_name(new_name):
                raise HTTPException(status_code=400, detail=f"服务器名称 '{new_name}' 已存在")

        # 解密前端发送的 ECC 加密密码
        if server_data.get('password'):
            try:
                server_data['password'] = crypto_manager.decrypt_password(server_data['password'])
            except Exception as e:
                log.error(f"解密服务器密码失败: {e}")
                raise HTTPException(status_code=400, detail="密码格式错误")

        success = await CM.update_server(server_name, server_data)
        if not success:
            raise HTTPException(status_code=500, detail="更新服务器配置失败")

        return {"status": "success", "message": f"服务器配置已更新"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"更新服务器配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/servers")
async def add_server_config(server_data: Dict[str, Any]):
    """添加新服务器"""
    try:
        # 检查名称是否已存在
        if CM.get_server_by_name(server_data.get('name')):
            raise HTTPException(status_code=400, detail="服务器名称已存在")

        # 解密前端发送的 ECC 加密密码
        if server_data.get('password'):
            try:
                server_data['password'] = crypto_manager.decrypt_password(server_data['password'])
            except Exception as e:
                log.error(f"解密服务器密码失败: {e}")
                raise HTTPException(status_code=400, detail="密码格式错误")

        await CM.add_server(server_data)
        return {"status": "success", "message": "服务器已添加"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"添加服务器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/config/servers/{server_name}")
async def delete_server_config(server_name: str):
    """删除服务器"""
    try:
        success = await CM.delete_server(server_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"服务器 {server_name} 不存在")

        return {"status": "success", "message": f"服务器 {server_name} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"删除服务器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config/synctasks")
async def get_synctasks_config():
    """获取所有同步任务配置（包含运行时状态）"""
    try:
        synctasks = []
        for task_name, task_obj in g.SYNC_TASKS.items():
            synctasks.append({
                'name': task_obj.name,
                'run': task_obj.is_run,
                'isfirst': task_obj.first,
                'which': task_obj.which,
                'status': task_obj.status
            })
        return {"synctasks": synctasks}
    except Exception as e:
        log.error(f"获取同步任务配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config/synctasks/{task_name}")
async def get_synctask_config(task_name: str):
    """获取单个同步任务配置"""
    try:
        task = CM.get_synctask_by_name(task_name)
        if task is None:
            raise HTTPException(status_code=404, detail=f"同步任务 {task_name} 不存在")
        return task
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"获取同步任务配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/config/synctasks/{task_name}")
async def update_synctask_config(task_name: str, task_data: Dict[str, Any]):
    """更新同步任务配置"""
    try:
        if task_data.get('name') != task_name:
            raise HTTPException(status_code=400, detail="任务名称不匹配")

        success = await CM.update_synctask(task_name, task_data)
        if not success:
            raise HTTPException(status_code=404, detail=f"同步任务 {task_name} 不存在")

        # 注意：任务刷新由 CM 的回调机制自动触发

        return {"status": "success", "message": f"同步任务 {task_name} 配置已更新"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"更新同步任务配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/synctasks")
async def add_synctask_config(task_data: Dict[str, Any]):
    """添加新同步任务"""
    try:
        if CM.get_synctask_by_name(task_data.get('name')):
            raise HTTPException(status_code=400, detail="同步任务名称已存在")

        await CM.add_synctask(task_data)
        return {"status": "success", "message": "同步任务已添加"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"添加同步任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/config/synctasks/{task_name}")
async def delete_synctask_config(task_name: str):
    """删除同步任务"""
    try:
        success = await CM.delete_synctask(task_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"同步任务 {task_name} 不存在")

        return {"status": "success", "message": f"同步任务 {task_name} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"删除同步任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config/env")
async def get_env_config():
    """获取环境配置"""
    try:
        return CM.get_env()
    except Exception as e:
        log.error(f"获取环境配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/config/env")
async def update_env_config(env_data: Dict[str, Any]):
    """更新整个环境配置"""
    try:
        await CM.update_env(env_data)
        return {"status": "success", "message": "环境配置已更新"}
    except Exception as e:
        log.error(f"更新环境配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 静态文件服务（用于前端）
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'frontend', 'dist')
if os.path.exists(frontend_path):
    from fastapi.responses import FileResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    # 挂载静态资源目录
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")

    # 404 异常处理器：支持 Vue Router history 模式
    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request, exc):
        """处理 404 错误，非 API 路径返回 index.html"""
        if exc.status_code == 404:
            # API 路径返回正常的 404 JSON 响应
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Not Found"}
                )

            # 检查是否是静态文件
            file_path = os.path.join(frontend_path, request.url.path.lstrip("/"))
            if os.path.isfile(file_path):
                return FileResponse(file_path)

            # 其他路径返回 index.html（让 Vue Router 处理）
            return FileResponse(os.path.join(frontend_path, "index.html"))

        # 其他 HTTP 异常正常返回
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)