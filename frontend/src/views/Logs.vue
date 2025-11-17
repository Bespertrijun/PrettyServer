<template>
  <div class="logs-page">
    <div class="page-header">
      <h1>日志管理</h1>
      <div class="header-actions">
        <el-select v-model="logLevel" placeholder="日志级别" style="width: 120px">
          <el-option label="全部" value="ALL" />
          <el-option label="DEBUG" value="DEBUG" />
          <el-option label="INFO" value="INFO" />
          <el-option label="WARNING" value="WARNING" />
          <el-option label="ERROR" value="ERROR" />
          <el-option label="CRITICAL" value="CRITICAL" />
        </el-select>
        <el-select v-model="logLines" placeholder="日志行数" style="width: 120px">
          <el-option label="100行" :value="100" />
          <el-option label="500行" :value="500" />
          <el-option label="1000行" :value="1000" />
        </el-select>
        <el-button type="primary" @click="refreshLogs">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-card>
      <div class="logs-container" v-loading="loading">
        <div
          v-for="(parsedLog, index) in parsedFilteredLogs"
          :key="index"
          class="log-line"
          :class="getLogLevelClass(parsedLog.level)"
        >
          <span class="log-time">{{ parsedLog.time }}</span>
          <span class="log-level">{{ parsedLog.level }}</span>
          <span class="log-module">{{ parsedLog.module }}</span>
          <span class="log-message">{{ parsedLog.message }}</span>
        </div>
        <div v-if="filteredLogs.length === 0" class="no-logs">
          暂无日志记录
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { logApi } from '@/api/services'
import { ElMessage } from 'element-plus'

const logs = ref<string[]>([])
const loading = ref(false)
const logLines = ref(100)
const logLevel = ref('ALL')

// 解析日志行
// 格式: 2025-10-07 00:00:01 - task.synctask:553 - INFO - Emby(home) / Emby(rn)：同步进度完毕，等待下一次运行
const parseLog = (log: string) => {
  const regex = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - ([^:]+:\d+) - (\w+) - (.+)$/
  const match = log.match(regex)

  if (match) {
    return {
      time: match[1],
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

// 过滤后的日志
const filteredLogs = computed(() => {
  if (logLevel.value === 'ALL') {
    return logs.value
  }
  return logs.value.filter(log => {
    const parsed = parseLog(log)
    return parsed.level === logLevel.value
  })
})

// 解析后的过滤日志（计算属性，带缓存）
const parsedFilteredLogs = computed(() => {
  return filteredLogs.value.map(log => parseLog(log))
})

const refreshLogs = async () => {
  loading.value = true
  try {
    const logData = await logApi.getLogs(logLines.value)
    logs.value = logData.logs.reverse() // 最新的在前
  } catch (error: any) {
    console.error('获取日志失败:', error)
    ElMessage.error('获取日志失败: '+ error.message)
  } finally {
    loading.value = false
  }
}

onMounted(refreshLogs)
</script>

<style scoped>
.logs-page {
  max-width: 1400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--el-text-color-primary);
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.logs-container {
  height: 600px;
  overflow-y: auto;
  padding: 15px;
  background-color: #1e1e1e;
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.log-line {
  padding: 6px 10px;
  font-size: 13px;
  line-height: 1.6;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 2px;
  border-radius: 3px;
  transition: opacity 0.2s;
}

.log-line:hover {
  opacity: 0.85;
}

.log-time {
  color: #868e96;
  min-width: 150px;
  font-size: 12px;
  flex-shrink: 0;
}

.log-level {
  min-width: 75px;
  text-align: center;
  font-weight: 600;
  font-size: 11px;
  flex-shrink: 0;
}

.log-module {
  color: #adb5bd;
  min-width: 180px;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}

.log-message {
  flex: 1;
  word-break: break-word;
}

/* 日志级别背景色 */
.log-debug {
  background-color: #2d2d2d;
  color: #868e96;
}

.log-info {
  background-color: #1e3a5f;
  color: #74c0fc;
}

.log-warning {
  background-color: #4a3a1a;
  color: #ffd93d;
}

.log-error {
  background-color: #4a1a1a;
  color: #ff6b6b;
}

.log-critical {
  background-color: #5a0a0a;
  color: #ff4444;
  font-weight: 600;
}

.log-default {
  background-color: #1e1e1e;
  color: #f8f9fa;
}

.no-logs {
  text-align: center;
  color: #868e96;
  padding: 40px 0;
}

@media (max-width: 768px) {
  .logs-container {
    height: 500px;
  }

  .log-line {
    flex-wrap: wrap;
    gap: 5px;
  }

  .log-time,
  .log-module {
    min-width: auto;
  }

  .log-message {
    width: 100%;
    margin-top: 5px;
  }
}
</style>