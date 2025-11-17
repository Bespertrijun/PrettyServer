// 库扫描配置项
export interface LibraryConfig {
  name: string
  crontab: string
}

// 任务配置
export interface TaskConfig {
  run: boolean
  crontab?: string
  library?: Record<string, LibraryConfig>  // scantask 专用的库配置，格式: { "库id": { name: "库名", crontab: "表达式" } }
}

// 服务器配置（对应 config.yaml 中的完整服务器配置）
export interface ServerConfig {
  name: string
  type: 'plex' | 'emby' | 'jellyfin'
  url: string
  token?: string
  username?: string  // Emby/Jellyfin 可选
  password?: string  // Emby/Jellyfin 可选
  roletask?: TaskConfig
  sorttask?: TaskConfig
  scantask?: TaskConfig
  mergetask?: TaskConfig  // Emby/Jellyfin 专用
  titletask?: TaskConfig  // Emby/Jellyfin 专用
}

// 服务器信息（运行时状态 + 可选的完整配置）
export interface ServerInfo {
  name: string
  type: 'plex' | 'emby' | 'jellyfin'
  url: string
  status: 'connected' | 'disconnected'
  config?: ServerConfig  // 按需加载的完整配置
}

// 系统状态枚举
export type SystemStatusEnum = 'healthy' | 'degraded' | 'error' | 'initializing'

// 系统状态
export interface SystemStatus {
  status: SystemStatusEnum
  servers_count: number
  failed_servers_count: number  // 失败服务器数量
  active_tasks: number
}

// 任务状态
export interface TaskStatus {
  server: string
  type: string
  tasks: {
    [key: string]: {
      enabled: boolean
      crontab: string
      last_run?: string
    }
  }
}

// 日志响应
export interface LogResponse {
  logs: string[]
}

// 服务器库信息
export interface Library {
  name: string
  id: string
}

// 同步任务状态
export type SyncTaskStatus = 'initializing' | 'running' | 'stopped' | 'failed'

// 观看同步任务配置
export interface SyncTask {
  name: string
  run: boolean
  isfirst: boolean
  which: string[]  // 两个服务器名称
  status?: SyncTaskStatus  // 任务运行状态（前端运行时状态，不存储在配置文件）
}

// 合集同步任务配置
export interface CollectionSyncTask {
  name: string
  run: boolean
  crontab: string
  which: string[]  // 两个服务器名称
  library_pairs: string[][]  // 库配对 [服务器A库名, 服务器B库名]
}

// 环境配置
export interface EnvConfig {
  tmdb_api: string
  concurrent_num: number
  proxy: {
    isproxy: boolean
    http: string
  }
  use_2fa?: boolean  // 是否启用双因素认证
}

// 通用响应
export interface ApiResponse {
  status: 'success' | 'error' | 'require_2fa'
  message: string
  data?: any
  username?: string  // 用于 require_2fa 状态
}