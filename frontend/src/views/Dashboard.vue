<template>
  <div class="dashboard">
    <el-row :gutter="20" class="status-cards">
      <el-col :span="8">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon class="card-icon"><Monitor /></el-icon>
              <span>系统状态</span>
            </div>
          </template>
          <div class="status-info">
            <div class="status-value" :class="getStatusClass()">
              {{ getStatusText() }}
            </div>
            <div class="status-time">
              上次更新：{{ formatTime(lastUpdateTime) }}
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon class="card-icon"><Cpu /></el-icon>
              <span>媒体服务器</span>
            </div>
          </template>
          <div class="status-info">
            <div class="status-value">{{ systemStatus.servers_count }}</div>
            <div class="status-label">
              {{ getServerStatusLabel() }}
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="status-card">
          <template #header>
            <div class="card-header">
              <el-icon class="card-icon"><Setting /></el-icon>
              <span>活跃任务</span>
            </div>
          </template>
          <div class="status-info">
            <div class="status-value">{{ systemStatus.active_tasks }}</div>
            <div class="status-label">个任务运行中</div>
          </div>
        </el-card>
      </el-col>

    </el-row>

    <el-row :gutter="20" class="content-row">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header card-header-with-action">
              <div class="header-title">
                <el-icon><List /></el-icon>
                <span>服务器列表</span>
              </div>
              <el-tooltip content="刷新">
                <el-button :icon="Refresh" circle size="small" @click="refreshServers" />
              </el-tooltip>
            </div>
          </template>
          <el-table :data="servers" style="width: 100%" v-loading="serversLoading">
            <el-table-column prop="name" label="名称" width="100" />
            <el-table-column prop="type" label="类型" width="80" />
            <el-table-column prop="url" label="地址" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="scope">
                <el-tag
                  :type="scope.row.status === 'connected' ? 'success' : 'danger'"
                  size="small"
                >
                  {{ scope.row.status === 'connected' ? '已连接' : '离线' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header card-header-with-action">
              <div class="header-title">
                <el-icon><Document /></el-icon>
                <span>最近日志</span>
              </div>
              <el-tooltip content="刷新">
                <el-button :icon="Refresh" circle size="small" @click="refreshLogs" />
              </el-tooltip>
            </div>
          </template>
          <div class="logs-container" v-loading="logsLoading">
            <div
              v-for="(parsedLog, index) in parsedLogs"
              :key="index"
              class="log-item"
              :class="getLogLevelClass(parsedLog.level)"
            >
              <span class="log-time">{{ parsedLog.time }}</span>
              <span class="log-level">{{ parsedLog.level }}</span>
              <span class="log-message">{{ parsedLog.message }}</span>
            </div>
            <div v-if="recentLogs.length === 0" class="no-logs">
              暂无日志记录
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Monitor, Cpu, Setting, List, Document, Refresh } from '@element-plus/icons-vue'
import { systemApi, serverApi, logApi } from '@/api/services'
import type { SystemStatus, ServerInfo, SystemStatusEnum } from '@/api/types'
import { ElMessage } from 'element-plus'
// 系统状态数据
const systemStatus = ref<SystemStatus>({
  status: 'initializing',
  servers_count: 0,
  failed_servers_count: 0,
  active_tasks: 0
})

// 最后更新时间
const lastUpdateTime = ref<string>(new Date().toISOString())

// 状态文本映射
const getStatusText = () => {
  const statusMap: Record<SystemStatusEnum, string> = {
    'healthy': '正常',
    'degraded': '部分失效',
    'error': '错误',
    'initializing': '初始化中'
  }
  return statusMap[systemStatus.value.status] || '未知'
}

// 状态颜色类名
const getStatusClass = () => {
  return `status-${systemStatus.value.status}`
}

// 服务器状态标签
const getServerStatusLabel = () => {
  const { servers_count, failed_servers_count } = systemStatus.value
  if (failed_servers_count > 0) {
    const healthy = servers_count - failed_servers_count
    return `${healthy} 个正常 / ${failed_servers_count} 个失败`
  }
  return `${servers_count} 个服务器已连接`
}

const servers = ref<ServerInfo[]>([])
const recentLogs = ref<string[]>([])
const serversLoading = ref(false)
const logsLoading = ref(false)

// 格式化时间
const formatTime = (isoString: string) => {
  return new Date(isoString).toLocaleString('zh-CN')
}

// 解析日志行
// 格式: 2025-10-07 00:00:01 - task.synctask:553 - INFO - Emby(home) / Emby(rn)：同步进度完毕，等待下一次运行
const parseLog = (log: string) => {
  const regex = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([^:]+:\d+) - (\w+) - (.+)$/
  const match = log.match(regex)

  if (match) {
    return {
      time: match[1].substring(11), // 只显示时间部分，不显示日期
      module: match[2],
      level: match[3],
      message: match[4]
    }
  }

  // 如果解析失败，返回原始内容
  return {
    time: '',
    module: '',
    level: '',
    message: log
  }
}

// 获取日志级别对应的样式类
const getLogLevelClass = (level: string) => {
  switch (level) {
    case 'DEBUG':
      return 'log-debug'
    case 'INFO':
      return 'log-info'
    case 'WARNING':
      return 'log-warning'
    case 'ERROR':
      return 'log-error'
    case 'CRITICAL':
      return 'log-critical'
    default:
      return 'log-default'
  }
}

// 解析后的日志列表（计算属性，带缓存）
const parsedLogs = computed(() => {
  return recentLogs.value.map(log => parseLog(log))
})

// 获取系统状态
const fetchSystemStatus = async () => {
  try {
    const status = await systemApi.getStatus()
    systemStatus.value = status
    // 更新前端的最后更新时间
    lastUpdateTime.value = new Date().toISOString()
  } catch (error: any) {
    console.error('获取系统状态失败:', error)
    ElMessage.error('获取系统状态失败: '+ error.message)
    // 后端未启动时显示默认状态
    systemStatus.value = {
      status: 'error',
      servers_count: 0,
      failed_servers_count: 0,
      active_tasks: 0
    }
    lastUpdateTime.value = new Date().toISOString()
  }
}

// 刷新服务器列表
const refreshServers = async () => {
  serversLoading.value = true
  try {
    const serverList = await serverApi.getServers()
    servers.value = serverList
  } catch (error: any) {
    console.error('获取服务器列表失败:', error)
    ElMessage.error('获取服务器列表失败: '+ error.message)
    // 显示示例数据
    servers.value = [
      {
        name: 'Demo Server',
        type: 'plex',
        url: 'http://localhost:32400',
        status: 'disconnected',
      }
    ]
  } finally {
    serversLoading.value = false
  }
}

// 刷新日志
const refreshLogs = async () => {
  logsLoading.value = true
  try {
    const logData = await logApi.getLogs(20)
    recentLogs.value = logData.logs.reverse() // 最新的在前
  } catch (error: any) {
    console.error('获取日志失败:', error)
    ElMessage.error('获取日志失败: '+ error.message)
    // 显示示例日志
    recentLogs.value = [
      "2025-10-07 00:00:01 - task.synctask:553 - ERROR - Emby(home) / Emby(rn)：同步进度完毕，等待下一次运行",
      "2025-10-07 00:00:56 - task.synctask:446 - INFO - Emby(home) / Emby(rn)：开始同步进度",
      "2025-10-07 00:01:01 - task.synctask:553 - WARNING - Emby(home) / Emby(rn)：同步进度完毕，等待下一次运行",
      "2025-10-07 00:01:56 - task.synctask:446 - INFO - Emby(home) / Emby(rn)：开始同步进度",
      "2025-10-07 00:02:03 - task.synctask:553 - INFO - Emby(home) / Emby(rn)：同步进度完毕，等待下一次运行",
      "2025-10-07 00:02:56 - task.synctask:446 - DEBUG - Emby(home) / Emby(rn)：开始同步进度",
      "2025-10-07 00:02:59 - task.synctask:553 - INFO - Emby(home) / Emby(rn)：同步进度完毕，等待下一次运行",
      "2025-10-07 00:03:56 - task.synctask:446 - INFO - Emby(home) / Emby(rn)：开始同步进度",
      "2025-10-07 00:04:00 - task.synctask:553 - CRITICAL - Emby(home) / Emby(rn)：同步进度完毕，等待下一次运行",
      "2025-10-07 00:04:56 - task.synctask:446 - INFO - Emby(home) / Emby(rn)：开始同步进度",
      "2025-10-07 00:05:08 - task.synctask:553 - INFO - Emby(home) / Emby(rn)：同步进度完毕，等待下一次运行",
    ]
  } finally {
    logsLoading.value = false
  }
}

// 初始化数据
const initData = async () => {
  await fetchSystemStatus()
  await refreshServers()
  await refreshLogs()
}

// 定时器 ID
let statusTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  initData()
  // 定时刷新系统状态
  statusTimer = setInterval(fetchSystemStatus, 30000) // 30秒刷新一次
})

// 组件卸载时清除定时器
onUnmounted(() => {
  if (statusTimer !== null) {
    clearInterval(statusTimer)
    statusTimer = null
  }
})
</script>

<style scoped>
.dashboard {
  width: 100%;
  max-width: none;
  margin: 0;
}

.status-cards {
  margin-bottom: 20px;
  display: flex;
  flex-wrap: wrap;
}

.status-cards :deep(.el-col) {
  display: flex;
}

.content-row {
  margin-bottom: 20px;
}

.status-card {
  text-align: center;
  min-height: 140px;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.status-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-header .card-icon {
  margin-right: 4px;
}

/* 带操作按钮的 header（服务器列表、日志等） */
.card-header-with-action {
  justify-content: center;
  align-items: center;
  width: 100%;
  position: relative;
}

.card-header-with-action .header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-header-with-action .el-button {
  position: absolute;
  right: 0;
}

.status-info {
  padding: 15px 0;
}

.status-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--el-color-primary);
  margin-bottom: 8px;
  line-height: 1;
}

.status-value.status-healthy {
  color: var(--el-color-success);
}

.status-value.status-degraded {
  color: var(--el-color-warning);
}

.status-value.status-error {
  color: var(--el-color-danger);
}

.status-value.status-initializing {
  color: var(--el-color-info);
}

.status-label {
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.status-time {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.logs-container {
  height: 350px;
  overflow-y: auto;
  padding: 12px;
  background-color: var(--el-fill-color-lighter);
  border-radius: 4px;
  font-size: 12px;
}

.log-item {
  padding: 6px 8px;
  margin-bottom: 3px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 11px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1.5;
  transition: opacity 0.2s;
}

.log-item:hover {
  opacity: 0.85;
}

.log-time {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  min-width: 65px;
  flex-shrink: 0;
}

.log-level {
  min-width: 70px;
  text-align: center;
  flex-shrink: 0;
  font-weight: 600;
  font-size: 10px;
}

.log-message {
  flex: 1;
  word-break: break-word;
  font-size: 11px;
}

/* 日志级别背景色 */
.log-debug {
  background-color: #f5f5f5;
  color: #909399;
}

.log-info {
  background-color: #e6f4ff;
  color: #409eff;
}

.log-warning {
  background-color: #fff4cc;
  color: #b8860b;
}

.log-error {
  background-color: #ffebeb;
  color: #f56c6c;
}

.log-critical {
  background-color: #ffe0e0;
  color: #d03050;
  font-weight: 600;
}

.log-default {
  background-color: #fafafa;
  color: #606266;
}

.no-logs {
  text-align: center;
  color: var(--el-text-color-placeholder);
  padding: 40px 0;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .status-value {
    font-size: 24px;
  }

  .logs-container {
    height: 300px;
  }
}

@media (max-width: 992px) {
  .dashboard :deep(.el-col) {
    margin-bottom: 15px;
  }

  .status-card {
    min-height: 120px;
  }

  .status-value {
    font-size: 20px;
  }

  .status-info {
    padding: 10px 0;
  }

  .logs-container {
    height: 250px;
    font-size: 11px;
  }
}

@media (max-width: 768px) {
  /* 移动端状态卡片改为两列布局 */
  .dashboard :deep(.status-cards .el-col) {
    flex: 0 0 50%;
    max-width: 50%;
  }

  .status-card {
    min-height: 100px;
    margin-bottom: 10px;
  }

  .status-value {
    font-size: 18px;
  }

  .status-label,
  .status-time {
    font-size: 11px;
  }

  /* 内容区域改为单列 */
  .dashboard :deep(.content-row .el-col) {
    flex: 0 0 100%;
    max-width: 100%;
    margin-bottom: 15px;
  }

  .logs-container {
    height: 200px;
  }

  .log-item {
    font-size: 10px;
  }
}

@media (max-width: 480px) {
  /* 小屏幕状态卡片改为单列 */
  .dashboard :deep(.status-cards .el-col) {
    flex: 0 0 100%;
    max-width: 100%;
  }

  .status-card {
    min-height: 80px;
    margin-bottom: 8px;
  }

  .card-header {
    font-size: 13px;
  }

  .status-value {
    font-size: 16px;
  }

  .status-info {
    padding: 8px 0;
  }

  .logs-container {
    height: 180px;
    padding: 8px;
  }

  .dashboard {
    padding: 0;
  }
}

/* 表格响应式 */
@media (max-width: 768px) {
  .dashboard :deep(.el-table) {
    font-size: 12px;
  }

  .dashboard :deep(.el-table .el-table__cell) {
    padding: 8px 4px;
  }
}
</style>