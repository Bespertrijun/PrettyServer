<template>
  <div class="sync-page">
    <div class="page-header">
      <h1>同步管理</h1>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="观看同步" name="watch">
        <el-card>
          <template #header>
            <div class="card-header">
              <h3>观看进度同步配置</h3>
              <el-button type="primary" @click="showAddSyncDialog = true">
                <el-icon><Plus /></el-icon>
                <span>添加同步任务</span>
              </el-button>
            </div>
          </template>

          <div v-if="syncTasks.length === 0" class="empty-container">
            <el-empty description="暂无观看同步任务" />
          </div>

          <div v-else class="tasks-container">
            <el-card
              v-for="task in syncTasks"
              :key="task.name"
              class="task-card"
            >
              <!-- 查看模式 -->
              <template v-if="editingTaskName !== task.name">
                <div class="task-card-header">
                  <div class="task-name">
                    <el-icon><Switch /></el-icon>
                    <span>{{ task.name }}</span>
                    <el-tag :type="task.run ? 'success' : 'info'" size="small" style="margin-left: 8px">
                      {{ task.run ? '已启用' : '已禁用' }}
                    </el-tag>
                    <el-tag
                      :type="getStatusTagType(task.status)"
                      size="small"
                      style="margin-left: 8px"
                      v-if="task.status"
                    >
                      {{ getStatusText(task.status) }}
                    </el-tag>
                  </div>
                  <div class="task-actions">
                    <el-button
                      type="primary"
                      size="small"
                      @click="startEdit(task)"
                    >
                      编辑
                    </el-button>
                    <el-button
                      type="danger"
                      size="small"
                      @click="handleDeleteSyncTask(task)"
                      :icon="Delete"
                      :loading="deletingTask[task.name]"
                    >
                      删除
                    </el-button>
                  </div>
                </div>

                <el-divider />

                <div class="task-info">
                  <div class="info-item">
                    <span class="info-label">首次同步:</span>
                    <el-tag :type="task.isfirst ? 'warning' : 'info'" size="small">
                      {{ task.isfirst ? '是（同步所有历史记录）' : '否（仅同步最近进度）' }}
                    </el-tag>
                  </div>
                  <div class="info-item">
                    <span class="info-label">同步服务器:</span>
                    <div class="server-tags">
                      <el-tag
                        v-for="serverName in task.which"
                        :key="serverName"
                        type="primary"
                        size="small"
                      >
                        {{ serverName }}
                      </el-tag>
                    </div>
                  </div>
                </div>
              </template>

              <!-- 编辑模式 -->
              <template v-else>
                <div class="task-card-header">
                  <div class="task-name">
                    <el-icon><Switch /></el-icon>
                    <span>{{ task.name }}</span>
                  </div>
                  <div class="task-actions">
                    <el-button
                      type="success"
                      size="small"
                      @click="saveEdit(task)"
                      :loading="savingTask[task.name]"
                    >
                      保存
                    </el-button>
                    <el-button
                      size="small"
                      @click="cancelEdit"
                    >
                      取消
                    </el-button>
                  </div>
                </div>

                <el-divider />

                <el-form :model="task" label-width="100px" size="small">
                  <el-form-item label="是否启用">
                    <el-switch v-model="task.run" />
                  </el-form-item>
                  <el-form-item label="首次同步">
                    <el-switch v-model="task.isfirst" />
                    <div class="form-tip">
                      开启后将同步所有历史观看记录，适合首次配置时使用
                    </div>
                  </el-form-item>
                  <el-form-item label="选择服务器" required>
                    <el-select
                      :ref="(el: any) => { if (el) editServerSelectRef = el }"
                      v-model="task.which"
                      multiple
                      clearable
                      placeholder="请选择两个服务器"
                      :disabled="loadingServers"
                      :multiple-limit="2"
                      style="width: 100%"
                      @change="handleEditServerChange"
                    >
                      <el-option
                        v-for="server in availableServers"
                        :key="server.name"
                        :label="`${server.name} (${server.type.toUpperCase()})`"
                        :value="server.name"
                        :disabled="!task.which.includes(server.name) && task.which.length >= 2"
                      />
                    </el-select>
                    <div class="form-tip">
                      请选择两个服务器进行观看进度同步（支持 Plex ↔ Emby/Jellyfin）
                    </div>
                  </el-form-item>
                </el-form>
              </template>
            </el-card>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="合集同步" name="collection">
        <el-card>
          <template #header>
            <h3>合集同步配置</h3>
          </template>
          <el-empty description="合集同步功能开发中..." />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加观看同步任务对话框 -->
    <el-dialog
      v-model="showAddSyncDialog"
      title="添加观看同步任务"
      :width="isMobile ? '95%' : '600px'"
      center
    >
      <el-form :model="newSyncTask" label-width="120px">
        <el-form-item label="任务名称" required>
          <el-input v-model="newSyncTask.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="newSyncTask.run" />
        </el-form-item>
        <el-form-item label="首次同步">
          <el-switch v-model="newSyncTask.isfirst" />
          <div class="form-tip">
            开启后将同步所有历史观看记录，适合首次配置时使用
          </div>
        </el-form-item>
        <el-form-item label="选择服务器" required>
          <el-select
            ref="serverSelectRef"
            v-model="newSyncTask.which"
            multiple
            clearable
            placeholder="请选择两个服务器"
            :disabled="loadingServers"
            :multiple-limit="2"
            style="width: 100%"
            @change="handleServerChange"
          >
            <el-option
              v-for="server in availableServers"
              :key="server.name"
              :label="`${server.name} (${server.type.toUpperCase()})`"
              :value="server.name"
              :disabled="!newSyncTask.which.includes(server.name) && newSyncTask.which.length >= 2"
            />
          </el-select>
          <div class="form-tip">
            请选择两个服务器进行观看进度同步（支持 Plex ↔ Emby/Jellyfin）
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddSyncDialog = false">取消</el-button>
        <el-button type="primary" @click="addSyncTask" :loading="addingTask">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Plus, Delete, Switch } from '@element-plus/icons-vue'
import { syncTaskApi, serverApi } from '@/api/services'
import type { SyncTask, ServerInfo, SyncTaskStatus } from '@/api/types'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('watch')
const syncTasks = ref<SyncTask[]>([])
const loadingServers = ref(false)
const showAddSyncDialog = ref(false)

// 服务器选择框的引用
const serverSelectRef = ref()

// 判断是否为移动端
const isMobile = ref(false)

// 检查屏幕宽度
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

// 监听窗口大小变化
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
const availableServers = ref<ServerInfo[]>([
  {
    "name": "1",
    "type": "plex" as 'plex' | 'emby' | 'jellyfin',
    "url": "string",
    "status": 'connected'
  }
])

const newSyncTask = ref<SyncTask>({
  name: '',
  run: true,
  isfirst: false,
  which: []
})

// 编辑相关状态
const editingTaskName = ref<string>('')
const taskBackup = ref<SyncTask | null>(null)
let editServerSelectRef: any = null

// Loading 状态
const addingTask = ref(false)
const savingTask = ref<Record<string, boolean>>({})
const deletingTask = ref<Record<string, boolean>>({})

// 加载观看同步任务列表
const loadSyncTasks = async () => {
  try {
    const response = await syncTaskApi.getSyncTasks()
    syncTasks.value = response.synctasks || []
  } catch (error: any) {
    console.error('加载观看同步任务失败:', error)
    ElMessage.error('加载观看同步任务失败: ' + error.message + '，请检查日志')
  }
}

// 加载可用服务器列表
const loadAvailableServers = async () => {
  loadingServers.value = true
  try {
    availableServers.value = await serverApi.getServers()
  } catch (error: any) {
    console.error('加载服务器列表失败:', error)
    ElMessage.error('加载服务器列表失败: ' + error.message + '，请检查日志')
  } finally {
    loadingServers.value = false
  }
}

// 添加观看同步任务
// 处理服务器选择变化
const handleServerChange = (value: string[]) => {
  // 当选择了两个服务器时，自动关闭下拉框
  if (value.length === 2 && serverSelectRef.value) {
    serverSelectRef.value.blur()
  }
}

// 处理编辑模式服务器选择变化
const handleEditServerChange = (value: string[]) => {
  // 当选择了两个服务器时，自动关闭下拉框
  if (value.length === 2 && editServerSelectRef) {
    editServerSelectRef.blur()
  }
}

const addSyncTask = async () => {
  // 表单验证
  if (!newSyncTask.value.name) {
    ElMessage.error('请输入任务名称')
    return
  }
  if (newSyncTask.value.which.length !== 2) {
    ElMessage.error('请选择两个服务器')
    return
  }

  addingTask.value = true
  try {
    const result = await syncTaskApi.addSyncTask(newSyncTask.value)
    if (result.status === 'success') {
      ElMessage.success('添加成功')
      showAddSyncDialog.value = false
      // 直接添加到列表
      syncTasks.value.push({ ...newSyncTask.value })
      // 重置表单
      newSyncTask.value = {
        name: '',
        run: true,
        isfirst: false,
        which: []
      }
    } else {
      ElMessage.error(result.message || '添加失败')
    }
  } catch (error: any) {
    console.error('添加观看同步任务失败:', error)
    ElMessage.error((error.message || '添加观看同步任务失败') + '，请检查日志')
  } finally {
    addingTask.value = false
  }
}

// 开始编辑任务
const startEdit = (task: SyncTask) => {
  editingTaskName.value = task.name
  // 备份当前数据，以便取消时恢复
  taskBackup.value = JSON.parse(JSON.stringify(task))
}

// 取消编辑
const cancelEdit = () => {
  if (taskBackup.value) {
    // 恢复原始数据
    const index = syncTasks.value.findIndex(t => t.name === editingTaskName.value)
    if (index !== -1) {
      syncTasks.value[index] = taskBackup.value
    }
  }
  editingTaskName.value = ''
  taskBackup.value = null
}

// 保存编辑
const saveEdit = async (task: SyncTask) => {
  // 验证
  if (task.which.length !== 2) {
    ElMessage.error('请选择两个服务器')
    return
  }

  savingTask.value[task.name] = true
  try {
    const result = await syncTaskApi.updateSyncTask(task.name, task)
    if (result.status === 'success') {
      ElMessage.success('保存成功')
      editingTaskName.value = ''
      taskBackup.value = null
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (error: any) {
    console.error('更新任务失败:', error)
    ElMessage.error('更新任务失败: ' + error.message + '，请检查日志')
  } finally {
    savingTask.value[task.name] = false
  }
}

// 删除观看同步任务
const handleDeleteSyncTask = async (task: SyncTask) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除观看同步任务 "${task.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    deletingTask.value[task.name] = true
    try {
      const result = await syncTaskApi.deleteSyncTask(task.name)
      if (result.status === 'success') {
        ElMessage.success('删除成功')
        // 直接从列表中移除
        const index = syncTasks.value.findIndex(t => t.name === task.name)
        if (index !== -1) {
          syncTasks.value.splice(index, 1)
        }
      } else {
        ElMessage.error(result.message || '删除失败')
      }
    } finally {
      deletingTask.value[task.name] = false
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除观看同步任务失败:', error)
      ElMessage.error('删除观看同步任务失败: ' + error.message + '，请检查日志')
    }
  }
}

// 获取状态显示文本
const getStatusText = (status?: SyncTaskStatus) => {
  const statusMap = {
    'initializing': '初始化中',
    'running': '运行中',
    'stopped': '未运行',
    'failed': '失败'
  }
  return status ? statusMap[status] : '未知'
}

// 获取状态标签类型
const getStatusTagType = (status?: SyncTaskStatus) => {
  const typeMap = {
    'initializing': 'warning',
    'running': 'success',
    'stopped': 'info',
    'failed': 'danger'
  }
  return status ? typeMap[status] : 'info'
}

onMounted(() => {
  loadSyncTasks()
  loadAvailableServers()
})
</script>

<style scoped>
.sync-page {
  max-width: 1200px;
}

.page-header {
  margin-bottom: 20px;
  color: var(--el-text-color-primary);
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--el-text-color-primary);
}

.empty-container {
  padding: 40px 0;
}

.tasks-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
}

.task-card {
  transition: all 0.3s ease;
}

.task-card:hover{
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.4);
}

.task-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.task-name .el-icon {
  font-size: 20px;
  color: var(--el-color-primary);
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  min-width: 80px;
}

.server-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .tasks-container {
    grid-template-columns: 1fr;
  }

  .task-card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .task-actions {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 480px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .card-header .el-button {
    width: 100%;
  }
}
</style>
