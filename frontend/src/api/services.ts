import api from './index'
import type {
  ServerInfo,
  ServerConfig,
  SystemStatus,
  TaskStatus,
  LogResponse,
  ApiResponse,
  SyncTask,
  CollectionSyncTask,
  Library,
  EnvConfig
} from './types'

// 认证相关
export const authApi = {
  // 登录
  login: (credentials: { username: string; password: string }): Promise<ApiResponse> =>
    api.post('/auth/login', credentials),

  // 登出
  logout: (): Promise<ApiResponse> =>
    api.post('/auth/logout'),

  // 检查登录状态
  getStatus: (): Promise<{ logged_in: boolean; username: string | null }> =>
    api.get('/auth/status'),

  // 修改密码
  changePassword: (data: { old_password: string; new_password: string }): Promise<ApiResponse> =>
    api.post('/auth/changepassword', data),

  // 启用双因素认证
  enable2FA: (): Promise<{ status: string; secret: string; qr_code: string; message: string }> =>
    api.post('/auth/2fa/enable'),

  // 验证并完成 2FA 绑定
  verify2FA: (code: string): Promise<ApiResponse> =>
    api.post('/auth/2fa/verify', { code }),

  // 禁用双因素认证
  disable2FA: (password: string): Promise<ApiResponse> =>
    api.post('/auth/2fa/disable', { password }),

  // 获取 2FA 状态
  get2FAStatus: (): Promise<{ enabled: boolean }> =>
    api.get('/auth/2fa/status'),
}

// 系统状态相关
export const systemApi = {
  // 获取系统状态
  getStatus: (): Promise<SystemStatus> => api.get('/status'),
}

// 服务器管理相关
export const serverApi = {
  // 获取所有服务器
  getServers: (): Promise<ServerInfo[]> => api.get('/servers'),

  // 获取单个服务器配置
  getServerConfig: (serverName: string): Promise<ServerConfig> =>
    api.get(`/config/servers/${serverName}`),

  // 添加服务器
  addServer: (serverData: ServerConfig): Promise<ApiResponse> =>
    api.post('/config/servers', serverData),

  // 更新服务器配置
  updateServer: (serverName: string, serverData: ServerConfig): Promise<ApiResponse> =>
    api.put(`/config/servers/${serverName}`, serverData),

  // 删除服务器
  deleteServer: (serverName: string): Promise<ApiResponse> =>
    api.delete(`/config/servers/${serverName}`),

  // 测试服务器连接
  testConnection: (serverName: string): Promise<ApiResponse> =>
    api.post('/servers/test', { name: serverName }),

  // 获取服务器库列表
  getServerLibraries: (serverName: string): Promise<{ libraries: Library[] }> =>
    api.get(`/servers/${serverName}/libraries`),
}

// 日志管理相关
export const logApi = {
  // 获取日志
  getLogs: (lines: number = 100): Promise<LogResponse> =>
    api.get(`/logs?lines=${lines}`),
}

// 同步任务管理相关
export const syncTaskApi = {
  // 获取所有观看同步任务
  getSyncTasks: (): Promise<{ synctasks: SyncTask[] }> =>
    api.get('/config/synctasks'),

  // 获取单个观看同步任务
  getSyncTask: (taskName: string): Promise<SyncTask> =>
    api.get(`/config/synctasks/${taskName}`),

  // 添加观看同步任务
  addSyncTask: (taskData: SyncTask): Promise<ApiResponse> =>
    api.post('/config/synctasks', taskData),

  // 更新观看同步任务
  updateSyncTask: (taskName: string, taskData: SyncTask): Promise<ApiResponse> =>
    api.put(`/config/synctasks/${taskName}`, taskData),

  // 删除观看同步任务
  deleteSyncTask: (taskName: string): Promise<ApiResponse> =>
    api.delete(`/config/synctasks/${taskName}`),

  // 获取所有合集同步任务
  getCollectionSyncTasks: (): Promise<{ collection_synctasks: CollectionSyncTask[] }> =>
    api.get('/config/collection-synctasks'),

  // 添加合集同步任务
  addCollectionSyncTask: (taskData: CollectionSyncTask): Promise<ApiResponse> =>
    api.post('/config/collection-synctasks', taskData),

  // 更新合集同步任务
  updateCollectionSyncTask: (taskName: string, taskData: CollectionSyncTask): Promise<ApiResponse> =>
    api.put(`/config/collection-synctasks/${taskName}`, taskData),

  // 删除合集同步任务
  deleteCollectionSyncTask: (taskName: string): Promise<ApiResponse> =>
    api.delete(`/config/collection-synctasks/${taskName}`),
}

// 配置管理相关
export const configApi = {
  // 获取环境配置
  getConfig: (): Promise<EnvConfig> =>
    api.get('/config/env'),

  // 更新环境配置
  updateConfig: (configData: EnvConfig): Promise<ApiResponse> =>
    api.put('/config/env', configData),
}