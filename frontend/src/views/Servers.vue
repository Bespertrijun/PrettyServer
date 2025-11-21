<template>
  <div class="servers-page">
    <div class="page-header">
      <h1>服务器管理</h1>
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><Plus /></el-icon>
        <span>添加服务器</span>
      </el-button>
    </div>

    <!-- 桌面端表格视图 -->
    <el-card v-if="!isMobile">
      <el-table
        ref="tableRef"
        :data="servers"
        v-loading="loading"
        row-key="name"
        @expand-change="handleExpandChange"
        @row-click="handleRowClick"
      >
        <el-table-column type="expand">
          <template #default="props">
            <div class="expand-content" v-loading="expandLoading[props.row.name]">
              <template v-if="editFormData[props.row.name]">
                <div class="edit-form-container">
                  <el-form :model="editFormData[props.row.name]" label-width="100px">
                    <h4>基本配置</h4>
                    <el-form-item label="服务器名称">
                      <el-input 
                      v-model="editFormData[props.row.name].name"
                      placeholder="不要重复"
                      />
                    </el-form-item>
                    <el-form-item label="类型">
                      <el-select v-model="editFormData[props.row.name].type">
                        <el-option label="Plex" value="plex" />
                        <el-option label="Emby" value="emby" />
                        <el-option label="Jellyfin" value="jellyfin" />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="服务器地址">
                      <div class="server-url-input">
                        <div class="url-row">
                          <el-select v-model="editFormData[props.row.name].protocol" placeholder="协议" class="url-protocol" >
                            <el-option label="http" value="http" />
                            <el-option label="https" value="https" />
                          </el-select>
                          <span class="url-separator">://</span>
                        </div>
                        <el-input v-model="editFormData[props.row.name].host" placeholder="localhost 或 IP" class="url-host"/>
                        <div class="url-row">
                          <span class="url-separator">:</span>
                          <el-input-number v-model="editFormData[props.row.name].port" :min="1" :max="65535" placeholder="端口" class="url-port" :controls="false" />
                        </div>
                      </div>
                    </el-form-item>
                    <el-form-item label="访问令牌">
                      <el-input v-model="editFormData[props.row.name].token" placeholder="Plex必填，emby / jellyfin选填Api key"/>
                    </el-form-item>
                    <el-form-item v-if="editFormData[props.row.name].type!=`plex`" label="用户名">
                      <el-input v-model="editFormData[props.row.name].username" placeholder="可选" />
                    </el-form-item>
                    <el-form-item v-if="editFormData[props.row.name].type!=`plex`" label="密码">
                      <el-input v-model="editFormData[props.row.name].password" type="password" show-password placeholder="可选" />
                    </el-form-item>

                    <h4 style="margin-top: 20px;">任务配置</h4>
                    <div class="task-configs-container">
                      <template v-for="(taskConfig, taskName) in editFormData[props.row.name]" :key="taskName">
                        <div v-if="taskConfig &&
                        typeof taskConfig === 'object' &&
                        'run' in taskConfig &&
                        shouldShowTask(editFormData[props.row.name].type, String(taskName))"
                        class="task-config-card"
                        :class="{ 'task-config-card-wide': taskName === 'scantask' }"
                        >
                          <div class="task-card-header">{{ formatTaskName(String(taskName)) }}</div>
                          <el-form-item label="是否启用">
                            <el-switch v-model="taskConfig.run" />
                          </el-form-item>

                          <!-- 非scantask显示普通crontab输入 -->
                          <el-form-item v-if="taskName !== 'scantask'" label="Crontab">
                            <el-input v-model="taskConfig.crontab" size="small" />
                          </el-form-item>

                          <!-- scantask显示库列表配置 -->
                           <template v-if="taskName === 'scantask'">
                            <div class="scantask-header">
                              <el-button
                                size="small"
                                type="primary"
                                :icon="Plus"
                                @click="addScanLibrary(props.row.name)"
                              >
                              添加库扫描配置
                              </el-button>
                            </div>
                            <div class="scantask-libraries">
                              <div
                                v-for="(libConfig, libId, idx) in taskConfig.library"
                                :key="idx"
                                class="scantask-library-row"
                              >
                                <div class="library-inputs">
                                  <el-select
                                    :model-value="libConfig.name ? libId : ''"
                                    @update:model-value="(val: string) => updateScanLibraryId(props.row.name, libId as string, val)"
                                    @click="loadLibrariesForSelect(props.row.name)"
                                    :loading="loadingLibraries[props.row.name]"
                                    placeholder="选择库"
                                    size="small"
                                    class="library-select"
                                  >
                                    <el-option
                                      v-for="lib in availableLibraries[props.row.name]"
                                      :key="lib.id"
                                      :label="lib.name"
                                      :value="lib.id"
                                      :disabled="isLibrarySelected(props.row.name, lib.id, libId as string)"
                                    />
                                  </el-select>
                                  <el-input
                                    v-model="libConfig.crontab"
                                    size="small"
                                    placeholder="输入Crontab表达式"
                                    class="crontab-input"
                                    required
                                  />
                                </div>
                                <el-button
                                  size="small"
                                  type="danger"
                                  :icon="Delete"
                                  circle
                                  @click="removeScanLibrary(props.row.name, libId as string)"
                                />
                              </div>
                            </div>
                          </template>
                        </div>
                      </template>
                    </div>

                    <div class="form-actions">
                      <el-button type="primary" @click="saveConfig(props.row)" :loading="savingConfig[props.row.name]">保存配置</el-button>
                    </div>
                  </el-form>
                </div>
              </template>
              <div v-else-if="expandError[props.row.name]" class="error-container">
                <div class="error-text">加载失败</div>
                <el-button
                  type="primary"
                  round
                  @click="LoadConfig(props.row)"
                >
                  重新加载
                </el-button>
              </div>
              <div v-else class="loading-text">加载配置中...</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="80" />
        <el-table-column prop="type" label="类型" min-width="80">
          <template #default="scope">
            <el-tag type="primary" size="small">{{ scope.row.type.toUpperCase() }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="url" label="地址" min-width="120" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" min-width="70" align="center">
          <template #default="scope">
            <!-- 大屏显示文字标签 -->
            <el-tag
              class="status-tag"
              :type="scope.row.status === 'connected' ? 'success' : 'danger'"
            >
              {{ scope.row.status === 'connected' ? '已连接' : '离线' }}
            </el-tag>
            <!-- 小屏显示圆点 -->
            <span
              class="status-dot"
              :class="scope.row.status === 'connected' ? 'status-connected' : 'status-disconnected'"
              :title="scope.row.status === 'connected' ? '已连接' : '离线'"
            ></span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="150">
          <template #default="scope">
            <el-tooltip content="测试连接" placement="top" :disabled="!isCompactMode">
              <el-button size="small" class="action-button" @click.stop="testConnection(scope.row)">
                <el-icon><Connection /></el-icon>
                <span class="button-text">测试连接</span>
              </el-button>
            </el-tooltip>
            <el-tooltip content="删除" placement="top" :disabled="!isCompactMode">
              <el-button size="small" type="danger" class="action-button" @click.stop="handleDelete(scope.row)" :loading="deletingServer[scope.row.name]">
                <el-icon><Delete /></el-icon>
                <span class="button-text">删除</span>
              </el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 移动端卡片视图 -->
    <div v-if="isMobile" v-loading="loading">
      <!-- 空状态提示 -->
      <el-empty v-if="!loading && servers.length === 0" description="暂无服务器" />

      <el-card
        v-for="server in servers"
        :key="server.name"
        class="server-card"
        :class="server.status === 'connected' ? 'server-card-connected' : 'server-card-disconnected'"
      >
        <div class="server-card-content" @click="toggleMobileExpand(server)">
          <div>
            <div class="server-card-title">
              <span class="server-name">{{ server.name }}</span>
              <el-tag type="primary" size="small" style="margin-left: 8px">{{ server.type.toUpperCase() }}</el-tag>
            </div>
            <div class="server-card-url">{{ server.url }}</div>
          </div>
          <div class="server-card-actions">
            <el-button size="small" @click.stop="testConnection(server)">测试连接</el-button>
            <el-button size="small" type="danger" @click.stop="handleDelete(server)" :loading="deletingServer[server.name]">删除</el-button>
          </div>
        </div>

        <!-- 展开配置区域 -->
        <div v-if="mobileExpanded[server.name]" class="expand-content" v-loading="expandLoading[server.name]">
          <template v-if="editFormData[server.name]">
            <div class="edit-form-container">
              <el-form :model="editFormData[server.name]" label-width="100px">
                <h4>基本配置</h4>
                <el-form-item label="服务器名称" required>
                  <el-input v-model="editFormData[server.name].name" />
                </el-form-item>
                <el-form-item label="类型">
                  <el-select v-model="editFormData[server.name].type">
                    <el-option label="Plex" value="plex" />
                    <el-option label="Emby" value="emby" />
                    <el-option label="Jellyfin" value="jellyfin" />
                  </el-select>
                </el-form-item>
                <el-form-item label="服务器地址">
                  <div class="server-url-input">
                    <div class="url-row">
                      <el-tooltip content="选择协议类型" placement="top">
                        <el-select v-model="editFormData[server.name].protocol" placeholder="协议" class="url-protocol">
                          <el-option label="http" value="http" />
                          <el-option label="https" value="https" />
                        </el-select>
                      </el-tooltip>
                      <span class="url-separator">://</span>
                    </div>
                    <el-tooltip content="输入服务器地址，例如：localhost 或 192.168.1.100" placement="top">
                      <el-input v-model="editFormData[server.name].host" placeholder="地址" class="url-host" />
                    </el-tooltip>
                    <div class="url-row">
                      <span class="url-separator">:</span>
                      <el-tooltip content="输入端口号（1-65535）" placement="top">
                        <el-input-number v-model="editFormData[server.name].port" :min="1" :max="65535" placeholder="端口" class="url-port" :controls="false" />
                      </el-tooltip>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="访问令牌">
                  <el-tooltip content="Plex 必须填写 X-Plex-Token，Emby/Jellyfin 填写 API Key" placement="top">
                    <el-input v-model="editFormData[server.name].token" placeholder="令牌"/>
                  </el-tooltip>
                </el-form-item>
                <el-form-item v-if="editFormData[server.name].type!=`plex`" label="用户名">
                  <el-input v-model="editFormData[server.name].username" placeholder="可选" />
                </el-form-item>
                <el-form-item v-if="editFormData[server.name].type!=`plex`" label="密码">
                  <el-input v-model="editFormData[server.name].password" type="password" show-password placeholder="可选" />
                </el-form-item>

                <h4 style="margin-top: 20px;">任务配置</h4>
                <div class="task-configs-container">
                  <template v-for="(taskConfig, taskName) in editFormData[server.name]" :key="taskName">
                    <div v-if="taskConfig &&
                    typeof taskConfig === 'object' &&
                    'run' in taskConfig &&
                    shouldShowTask(editFormData[server.name].type, String(taskName))"
                    class="task-config-card"
                    :class="{ 'task-config-card-wide': taskName === 'scantask' }"
                    >
                      <div class="task-card-header">{{ formatTaskName(String(taskName)) }}</div>
                      <el-form-item label="是否启用">
                        <el-switch v-model="taskConfig.run" />
                      </el-form-item>

                      <!-- 非scantask显示普通crontab输入 -->
                      <el-form-item v-if="taskName !== 'scantask'" label="Crontab">
                        <el-input v-model="taskConfig.crontab" size="small" />
                      </el-form-item>

                      <!-- scantask显示库列表配置 -->
                      <template v-if="taskName === 'scantask'">
                        <div class="scantask-header">
                          <el-button
                            size="small"
                            type="primary"
                            :icon="Plus"
                            @click="addScanLibrary(server.name)"
                          >
                            添加库扫描配置
                          </el-button>
                        </div>
                        <div class="scantask-libraries">
                          <div
                            v-for="(libConfig, libId, idx) in taskConfig.library"
                            :key="idx"
                            class="scantask-library-row"
                          >
                            <div class="library-inputs">
                              <el-select
                                :model-value="libConfig.name ? libId : ''"
                                @update:model-value="(val: string) => updateScanLibraryId(server.name, libId as string, val)"
                                @click="loadLibrariesForSelect(server.name)"
                                :loading="loadingLibraries[server.name]"
                                placeholder="选择库"
                                size="small"
                                class="library-select"
                              >
                                <el-option
                                  v-for="lib in availableLibraries[server.name]"
                                  :key="lib.id"
                                  :label="lib.name"
                                  :value="lib.id"
                                  :disabled="isLibrarySelected(server.name, lib.id, libId as string)"
                                />
                              </el-select>
                              <el-input
                                v-model="libConfig.crontab"
                                size="small"
                                placeholder="输入Crontab表达式"
                                class="crontab-input"
                              />
                            </div>
                            <el-button
                              size="small"
                              type="danger"
                              :icon="Delete"
                              circle
                              @click="removeScanLibrary(server.name, libId as string)"
                            />
                          </div>
                        </div>
                      </template>
                    </div>
                  </template>
                </div>

                <div class="form-actions">
                  <el-button type="primary" @click="saveConfig(server)" :loading="savingConfig[server.name]">保存配置</el-button>
                </div>
              </el-form>
            </div>
          </template>
          <div v-else-if="expandError[server.name]" class="error-container">
            <div class="error-text">加载失败</div>
            <el-button
              type="primary"
              round
              @click="LoadConfig(server)"
            >
              重新加载
            </el-button>
          </div>
          <div v-else class="loading-text">加载配置中...</div>
        </div>
      </el-card>
    </div>

    <!-- 添加服务器对话框 -->
    <el-dialog
      v-model="showAddDialog"
      title="添加服务器"
      width="600px"
      center
      class="server-dialog"
    >
      <el-form :model="newServer" label-width="100px">
        <el-form-item label="服务器名称" required>
          <el-input v-model="newServer.name" placeholder="请输入服务器名称" />
        </el-form-item>
        <el-form-item label="服务器类型" required>
          <el-select v-model="newServer.type" placeholder="选择服务器类型" class="server-type-select">
            <el-option label="Plex" value="plex" />
            <el-option label="Emby" value="emby" />
            <el-option label="Jellyfin" value="jellyfin" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务器地址" required>
          <div class="server-url-input">
            <div class="url-row">
              <el-tooltip v-if="isMobile" content="选择协议类型" placement="top">
                <el-select v-model="newServer.protocol" placeholder="协议" class="url-protocol">
                  <el-option label="http" value="http" />
                  <el-option label="https" value="https" />
                </el-select>
              </el-tooltip>
              <el-select v-else v-model="newServer.protocol" placeholder="协议" class="url-protocol">
                <el-option label="http" value="http" />
                <el-option label="https" value="https" />
              </el-select>
              <span class="url-separator">://</span>
            </div>
            <el-tooltip v-if="isMobile" content="输入服务器地址，例如：localhost 或 192.168.1.100" placement="top">
              <el-input v-model="newServer.host" placeholder="地址" class="url-host" />
            </el-tooltip>
            <el-input v-else v-model="newServer.host" placeholder="localhost 或 IP" class="url-host" />
            <div class="url-row">
              <span class="url-separator">:</span>
              <el-tooltip v-if="isMobile" content="输入端口号（1-65535）" placement="top">
                <el-input-number v-model="newServer.port" :min="1" :max="65535" placeholder="端口" class="url-port" :controls="false" />
              </el-tooltip>
              <el-input-number v-else v-model="newServer.port" :min="1" :max="65535" placeholder="端口" class="url-port" :controls="false" />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="访问令牌">
          <el-tooltip v-if="isMobile" content="Plex 必须填写 X-Plex-Token，Emby/Jellyfin 填写 API Key" placement="top">
            <el-input v-model="newServer.token" placeholder="令牌" />
          </el-tooltip>
          <el-input v-else v-model="newServer.token" placeholder="Plex必填，emby / jellyfin选填Api key" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="newServer.username" placeholder="可选" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="newServer.password" type="password" show-password placeholder="可选" />
        </el-form-item>

        <!-- 任务配置（根据服务器类型动态显示） -->
        <template v-if="newServer.type">
          <h4 style="margin-top: 20px; margin-bottom: 16px;">任务配置</h4>
          <div class="task-configs-container">
            <template v-for="(taskConfig, taskName) in newServer.tasks" :key="taskName">
              <div class="task-config-card" :class="{ 'task-config-card-wide': taskName === 'scantask' }">
                <div class="task-card-header">{{ formatTaskName(String(taskName)) }}</div>
                <el-form-item label="是否启用">
                  <el-switch v-model="taskConfig.run" />
                </el-form-item>

                <!-- 非scantask显示普通crontab输入 -->
                <el-form-item v-if="taskName !== 'scantask'" label="Crontab">
                  <el-input v-model="taskConfig.crontab" size="small" placeholder="如: 0 0 * * *" />
                </el-form-item>

                <!-- scantask显示库列表配置 -->
                <template v-if="taskName === 'scantask'">
                  <div class="scantask-header">
                    <el-tooltip
                      content="请先保存服务器后再配置库扫描"
                      placement="top"
                    >
                      <el-button
                        size="small"
                        type="primary"
                        :icon="Plus"
                        disabled
                      >
                        添加库扫描配置
                      </el-button>
                    </el-tooltip>
                  </div>
                  <div class="scantask-libraries">
                    <div
                      v-for="(libConfig, libId, idx) in (taskConfig.library as Record<string, LibraryConfig>)"
                      :key="idx"
                      class="scantask-library-row"
                    >
                      <div class="library-inputs">
                        <el-select
                          :model-value="libConfig.name ? libId : ''"
                          @update:model-value="(val: string) => updateScanLibraryId(newServer.name, libId as string, val)"
                          @click="loadLibrariesForSelect(newServer.name)"
                          :loading="loadingLibraries[newServer.name]"
                          placeholder="选择库"
                          size="small"
                          class="library-select"
                        >
                          <el-option
                            v-for="lib in availableLibraries[newServer.name]"
                            :key="lib.id"
                            :label="lib.name"
                            :value="lib.id"
                            :disabled="isLibrarySelected(newServer.name, lib.id, libId as string)"
                          />
                        </el-select>
                        <el-input
                          v-model="libConfig.crontab"
                          size="small"
                          placeholder="输入Crontab表达式"
                          class="crontab-input"
                        />
                      </div>
                      <el-button
                        size="small"
                        type="danger"
                        :icon="Delete"
                        circle
                        @click="removeScanLibrary(newServer.name, libId as string)"
                      />
                    </div>
                  </div>
                </template>
              </div>
            </template>
          </div>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false" :disabled="addingServer">取消</el-button>
        <el-button type="primary" @click="addServer" :loading="addingServer">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Plus, Connection, Delete } from '@element-plus/icons-vue'
import { serverApi } from '@/api/services'
import type { ServerInfo, ServerConfig, Library, LibraryConfig } from '@/api/types'
import { ElMessageBox, ElMessage } from 'element-plus'
import { encryptPassword } from '@/utils/crypto'

const servers = ref<ServerInfo[]>([])

const loading = ref(false)
const showAddDialog = ref(false)

// 判断是否为移动端
const isMobile = ref(false)

// 判断是否为紧凑模式（显示图标）
const isCompactMode = ref(false)

// 表格引用
const tableRef = ref()

// 展开行加载状态
const expandLoading = ref<Record<string, boolean>>({})

// 展开行错误状态
const expandError = ref<Record<string, boolean>>({})

// 删除按钮加载状态
const deletingServer = ref<Record<string, boolean>>({})

// 编辑表单数据（每行的配置副本）
// 编辑表单数据（扩展了 URL 拆分字段）
const editFormData = ref<Record<string, ServerConfig & { protocol?: string; host?: string; port?: number }>>({})

// 移动端展开的服务器
const mobileExpanded = ref<Record<string, boolean>>({})

const newServer = ref({
  name: '',
  type: '',
  protocol: 'http',
  host: '',
  port: 80,
  token: '',
  username: '',
  password: '',
  tasks: {} as Record<string, any>
})

// 库扫描配置相关状态
const availableLibraries = ref<Record<string, Library[]>>({})
const loadingLibraries = ref<Record<string, boolean>>({})

// 保存和添加操作的 loading 状态
const savingConfig = ref<Record<string, boolean>>({})
const addingServer = ref(false)

const loadServers = async () => {
  loading.value = true
  try {
    servers.value = await serverApi.getServers()
  } catch (error: any) {
    console.error('加载服务器列表失败:', error)
    ElMessage.error('加载服务器失败: '+ error.message + '，请检查日志')
  } finally {
    loading.value = false
  }
}

const testConnection = async (server: ServerInfo) => {
  try {
    const result = await serverApi.testConnection(server.name)

    // 根据后端返回的 status 显示消息
    if (result.status === 'success') {
      ElMessage.success(result.message)
    } else {
      ElMessage.error((result.message || '连接测试失败')+ '，请检查日志')
    }
  } catch (error: any) {
    console.error('测试连接失败:', error)
    ElMessage.error('测试连接失败: ' + (error.message || '连接测试失败') + '，请检查日志')
  }
}

const addServer = async () => {
  // 表单验证
  if (!newServer.value.name || !newServer.value.type || !newServer.value.host || !newServer.value.port) {
    ElMessage.error('请填写所有必填项（名称、类型、主机地址、端口）')
    return
  }

  addingServer.value = true
  try {
    // 组合完整的 URL
    const url = `${newServer.value.protocol}://${newServer.value.host}:${newServer.value.port}`

    // 加密密码（如果存在）
    let encryptedPassword = newServer.value.password
    if (encryptedPassword) {
      try {
        encryptedPassword = await encryptPassword(encryptedPassword)
      } catch (error) {
        console.error('密码加密失败:', error)
        ElMessage.error('密码加密失败，请重试')
        return
      }
    }

    // 合并基本信息和任务配置
    const serverData: ServerConfig = {
      name: newServer.value.name,
      type: newServer.value.type as 'plex' | 'emby' | 'jellyfin',
      url: url,
      token: newServer.value.token,
      username: newServer.value.username,
      password: encryptedPassword,
      ...newServer.value.tasks
    }

    // 调用 API 添加服务器
    const result = await serverApi.addServer(serverData)

    if (result.status === 'success') {
      ElMessage.success(result.message || '添加服务器成功')
      // 重新加载服务器列表
      await loadServers()
      // 关闭对话框
      showAddDialog.value = false
      // 重置表单
      newServer.value = {
        name: '',
        type: '',
        protocol: 'http',
        host: '',
        port: 80,
        token: '',
        username: '',
        password: '',
        tasks: {}
      }
    } else {
      ElMessage.error(result.message || '添加服务器失败')
    }
  } catch (error: any) {
    console.error('添加服务器失败:', error)
    ElMessage.error('添加服务器失败: '+ (error.message || '添加服务器失败') + '，请检查日志')
  } finally {
    addingServer.value = false
  }
}

// 删除服务器
const handleDelete = async (server: ServerInfo) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除服务器 "${server.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    // 用户确认后执行删除
    deletingServer.value[server.name] = true
    try {
      const result = await serverApi.deleteServer(server.name)

      if (result.status === 'success') {
        ElMessage.success(result.message)
        // 从本地列表中移除
        servers.value = servers.value.filter(s => s.name !== server.name)
      } else {
        ElMessage.error(result.message || '删除失败')
      }
    } finally {
      deletingServer.value[server.name] = false
    }
  } catch (error: any) {
    // 用户点击取消或发生错误
    if (error !== 'cancel') {
      console.error('删除服务器失败:', error)
      ElMessage.error('删除服务器失败: '+ (error.message || '删除服务器失败') + '，请检查日志')
    }
  }
}

// 处理行点击事件（点击任意位置切换展开状态）
const handleRowClick = (row: ServerInfo) => {
  if (tableRef.value) {
    tableRef.value.toggleRowExpansion(row)
  }
}

// 处理表格展开事件
const handleExpandChange = async (row: ServerInfo, expandedRows: any[]) => {
  // 如果是展开操作且还没有加载过配置
  if (expandedRows.some(r => r.name === row.name) && !row.config) {
    LoadConfig(row)
  }
}

// 移动端切换展开/收起
const toggleMobileExpand = (server: ServerInfo) => {
  // 切换展开状态
  mobileExpanded.value[server.name] = !mobileExpanded.value[server.name]

  // 如果是展开操作且还没有加载过配置，则加载配置
  if (mobileExpanded.value[server.name] && !server.config) {
    LoadConfig(server)
  }
}

// 重试加载配置
const LoadConfig = async (row: ServerInfo) => {
  expandLoading.value[row.name] = true
  expandError.value[row.name] = false
    try {
      // 调用 API 获取服务器完整配置
      const config = await serverApi.getServerConfig(row.name)
      // 将配置存储到 ServerInfo 的 config 字段
      row.config = config
      // 创建配置副本供编辑使用
      const editData = JSON.parse(JSON.stringify(config))

      // 解析 URL 为 protocol、host、port
      if (editData.url) {
        try {
          const urlObj = new URL(editData.url)
          editData.protocol = urlObj.protocol.replace(':', '')
          editData.host = urlObj.hostname
          editData.port = parseInt(urlObj.port) || (urlObj.protocol === 'https:' ? 443 : 80)
        } catch (e) {
          console.error('URL 解析失败:', e)
          editData.protocol = 'http'
          editData.host = ''
          editData.port = 80
        }
      }

      editFormData.value[row.name] = editData
    } catch (error : any) {
      console.error('获取服务器配置失败:', error)
      ElMessage.error('获取服务器配置失败: '+ error.message + '，请检查日志')
      // 标记加载失败
      expandError.value[row.name] = true
    } finally {
      expandLoading.value[row.name] = false
    }
}

// 保存配置
const saveConfig = async (row: ServerInfo) => {
  const formData = editFormData.value[row.name]
  if (!formData) return

  // 必填项检查
  if (!formData.name || !formData.type || !formData.host || !formData.port) {
    ElMessage.error('请填写所有必填项（名称、类型、主机地址、端口）')
    return
  }

  savingConfig.value[row.name] = true
  try {
    // 组合完整的 URL
    formData.url = `${formData.protocol}://${formData.host}:${formData.port}`

    // 处理用户名：如果为空，删除字段保持原值
    if (!formData.username) {
      delete formData.username
    }

    // 加密密码（如果存在且不为空）
    if (formData.password) {
      try {
        formData.password = await encryptPassword(formData.password)
      } catch (error) {
        console.error('密码加密失败:', error)
        ElMessage.error('密码加密失败，请重试')
        savingConfig.value[row.name] = false
        return
      }
    } else {
      // 如果密码为空，删除密码字段，保持原密码不变
      delete formData.password
    }

    // 清理 scantask 中的空配置
    if (formData.scantask?.library) {
      const cleanedLibrary: Record<string, any> = {}
      Object.entries(formData.scantask.library).forEach(([id, config]) => {
        // 过滤掉：1) name为空 2) id是临时id且未选择库
        if (config.name && !id.startsWith('temp_')) {
          cleanedLibrary[id] = config
        }
      })
      formData.scantask.library = cleanedLibrary
    }

    const result = await serverApi.updateServer(row.name, formData)

    if (result.status === 'success') {
      // 保存成功后，同步更新 ServerInfo 和 config
      row.name = formData.name
      row.type = formData.type
      row.url = formData.url
      row.config = JSON.parse(JSON.stringify(formData))

      // 重新克隆到编辑表单，确保数据一致
      editFormData.value[formData.name] = JSON.parse(JSON.stringify(formData))

      // 如果服务器名称改变了，需要删除旧的 editFormData
      if (row.name !== formData.name) {
        delete editFormData.value[row.name]
      }

      ElMessage.success('配置保存成功')
    } else {
      ElMessage.error(result.message || '保存失败')
    }
  } catch (error: any) {
    console.error('保存配置失败:', error)
    ElMessage.error('保存配置失败: '+ (error.message || '保存配置失败') + '，请检查日志')
  } finally {
    savingConfig.value[row.name] = false
  }
}

// 格式化任务名称
const formatTaskName = (taskName: string): string => {
  const taskNameMap: Record<string, string> = {
    'roletask': '演员本地化',
    'sorttask': '标题排序',
    'scantask': '库扫描',
    'mergetask': '电影合并',
    'titletask': '季度标题'
  }
  return taskNameMap[taskName] || taskName
}

// 判断任务是否应该显示（根据服务器类型）
const shouldShowTask = (serverType: string, taskName: string): boolean => {
  const tasksByType: Record<string, string[]> = {
    'plex': ['roletask', 'sorttask', 'scantask'],
    'emby': ['roletask', 'sorttask', 'scantask', 'mergetask', 'titletask'],
    'jellyfin': ['sorttask', 'scantask', 'mergetask', 'titletask']
  }

  const allowedTasks = tasksByType[serverType.toLowerCase()]
  return allowedTasks ? allowedTasks.includes(taskName) : true
}

// 根据服务器类型生成默认任务配置
const generateDefaultTasks = (serverType: string): Partial<ServerConfig> => {
  const defaultTaskConfig = {
    run: false,
    crontab: '0 0 * * *'
  }

  const tasksByType: Record<string, string[]> = {
    'plex': ['roletask', 'sorttask', 'scantask'],
    'emby': ['roletask', 'sorttask', 'scantask', 'mergetask', 'titletask'],
    'jellyfin': ['sorttask', 'scantask', 'mergetask', 'titletask']
  }

  const allowedTasks = tasksByType[serverType.toLowerCase()] || []
  const tasks: any = {}

  allowedTasks.forEach(taskName => {
    if (taskName === 'scantask') {
      tasks[taskName] = {
        ...defaultTaskConfig,
        library: {}
      }
    } else {
      tasks[taskName] = { ...defaultTaskConfig }
    }
  })

  return tasks
}

// 添加库扫描行（支持编辑和新增）
const addScanLibrary = (serverName: string) => {
  // 优先从 editFormData 获取，如果没有则从 newServer 获取
  let scantask
  if (editFormData.value[serverName]) {
    scantask = editFormData.value[serverName]?.scantask
  } else if (serverName === newServer.value.name) {
    scantask = newServer.value.tasks?.scantask
  }

  if (!scantask) return

  if (!scantask.library) {
    scantask.library = {}
  }
  // 生成唯一的临时id（使用时间戳 + 随机数）
  const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  scantask.library[tempId] = { name: '', crontab: '' }
}

// 点击select时加载库列表
const loadLibrariesForSelect = async (serverName: string) => {
  if (availableLibraries.value[serverName]) return // 已加载过

  loadingLibraries.value[serverName] = true
  try {
    const response = await serverApi.getServerLibraries(serverName)
    availableLibraries.value[serverName] = response.libraries
  } catch (error: any) {
    console.error('加载服务器库列表失败:', error)
    ElMessage.error('加载库列表失败: ' + error.message + '，请检查日志')
  } finally {
    loadingLibraries.value[serverName] = false
  }
}

// 更新库扫描的库ID（更换选择的库，支持编辑和新增）
const updateScanLibraryId = (serverName: string, oldId: string, newId: string) => {
  // 优先从 editFormData 获取，如果没有则从 newServer 获取
  let scantask
  if (editFormData.value[serverName]) {
    scantask = editFormData.value[serverName]?.scantask
  } else if (serverName === newServer.value.name) {
    scantask = newServer.value.tasks?.scantask
  }

  if (!scantask || !scantask.library || !scantask.library[oldId]) return

  // 获取旧配置
  const oldConfig = scantask.library[oldId]

  // 查找新选择的库的name
  const newLibrary = availableLibraries.value[serverName]?.find(lib => lib.id === newId)
  if (!newLibrary) return

  // 删除旧的id，添加新的id
  delete scantask.library[oldId]
  scantask.library[newId] = {
    name: newLibrary.name,
    crontab: oldConfig.crontab // 保留原来的crontab
  }
}

// 删除库扫描行（支持编辑和新增）
const removeScanLibrary = (serverName: string, libId: string) => {
  // 优先从 editFormData 获取，如果没有则从 newServer 获取
  let scantask
  if (editFormData.value[serverName]) {
    scantask = editFormData.value[serverName]?.scantask
  } else if (serverName === newServer.value.name) {
    scantask = newServer.value.tasks?.scantask
  }

  if (!scantask || !scantask.library) return

  delete scantask.library[libId]
}

// 判断某个库是否已被选择（支持编辑和新增）
const isLibrarySelected = (serverName: string, libId: string, currentLibId: string) => {
  // 优先从 editFormData 获取，如果没有则从 newServer 获取
  let scantask
  if (editFormData.value[serverName]) {
    scantask = editFormData.value[serverName]?.scantask
  } else if (serverName === newServer.value.name) {
    scantask = newServer.value.tasks?.scantask
  }

  if (!scantask?.library) return false

  // 如果是当前行，不禁用
  if (currentLibId === libId) return false

  // 检查其他行是否已选择该库
  return Object.keys(scantask.library).some(id => id === libId && id !== currentLibId)
}

// 检查窗口大小
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 600
  isCompactMode.value = window.innerWidth <= 980
}

onMounted(() => {
  loadServers()
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

// 监听服务器类型变化，自动生成对应的任务配置
watch(() => newServer.value.type, (newType) => {
  if (newType) {
    newServer.value.tasks = generateDefaultTasks(newType)
  }
})

</script>

<style scoped>
.servers-page {
  width: 100%;
  max-width: none;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: var(--el-text-color-primary);
}

.expand-content {
  padding: 20px;
  background-color: var(--el-fill-color-lighter);
  border-radius: 4px;
  margin: 30px 0;
}

.expand-content h4 {
  margin: 0 0 15px 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
  font-weight: 600;
}

.config-section {
  margin-bottom: 20px;
}

.config-section:last-child {
  margin-bottom: 0;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
  margin-bottom: 15px;
}

.config-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background-color: var(--el-bg-color);
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
}

.config-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
  font-weight: 500;
  min-width: 80px;
  margin-right: 12px;
}

.config-value {
  font-size: 13px;
  color: var(--el-text-color-primary);
  word-break: break-all;
}

.token-value {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  color: var(--el-text-color-secondary);
}

.tasks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 10px;
}

.task-item {
  padding: 12px;
  background-color: var(--el-bg-color);
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.task-detail {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.task-cron {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.task-name {
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.no-tasks {
  text-align: center;
  color: var(--el-text-color-placeholder);
  padding: 20px;
  font-size: 13px;
  grid-column: 1 / -1;
}

.loading-text {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 20px;
  font-size: 13px;
}

.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  gap: 12px;
}

.error-text {
  color: var(--el-color-danger);
  font-size: 13px;
}

.config-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.edit-form-container {
  padding: 16px;
}

.edit-form-container h4 {
  margin: 0 0 16px 0;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

/* 服务器地址输入框样式 */
.server-url-input {
  display: flex;
  gap: 8px;
  align-items: center;
}

.url-row {
  display: contents;
}

.url-protocol {
  flex: 1;
  min-width: 70px;
}

.url-host {
  flex: 3;
  min-width: 100px;
}

.url-port {
  flex: 1;
  min-width: 70px;
}

.url-separator {
  color: var(--el-text-color-regular);
}

/* 移动端响应式 - 垂直布局 */
@media (max-width: 768px) {
  .server-url-input {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .url-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .url-protocol,
  .url-host,
  .url-port {
    flex: 1;
    min-width: 0;
    width: 100%;
  }
}

.server-info {
  padding: 8px 12px;
  background-color: var(--el-bg-color);
  border-radius: 4px;
  font-size: 12px;
}

.info-label {
  color: var(--el-text-color-secondary);
  margin-right: 8px;
}

.info-value {
  color: var(--el-text-color-primary);
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.status-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

/* 表格中的状态圆点默认隐藏 */
.el-table .status-dot {
  display: none;
}

/* 默认：操作列按钮只显示文字，隐藏图标 */
.el-table .action-button .el-icon {
  display: none;
}

.status-connected {
  background-color: var(--el-color-success);
  box-shadow: 0 0 4px var(--el-color-success);
}

.status-disconnected {
  background-color: var(--el-color-danger);
  box-shadow: 0 0 4px var(--el-color-danger);
}

/* 移动端卡片样式 */
.server-card {
  margin-bottom: 16px;
  transition: all 0.3s ease;
}

/* 覆盖 el-card 默认的 padding-bottom，让 content 区域能延伸到底 */
.server-card :deep(.el-card__body) {
  padding: 0;
}

.server-card:hover{
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.4);
}

/* 卡片状态：通过头部和操作区域的背景色和边框表示 */
.server-card-connected .server-card-content {
  background: linear-gradient(135deg, #f0fdf4 0%, #acfec9 100%);
  border-left: 4px solid var(--el-color-success);
}

.server-card-disconnected .server-card-content {
  background: linear-gradient(135deg, #fef2f2 0%, #ff9595 100%);
  border-left: 4px solid var(--el-color-danger);
}

.server-card-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 20px 20px;
  cursor: pointer;
  border-radius: 4px 4px 0 0;
}

.server-card-title {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.server-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.server-card-url {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}

/* 展开内容：添加上边距与content区分开 */
.server-card .expand-content {
  margin: 20px 20px;
}

/* 任务配置卡片布局 */
.task-configs-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.task-config-card {
  flex: 1 1 calc(33.33% - 7px);
  min-width: 180px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background-color: var(--el-fill-color-light);
  transition: all 0.3s ease;
}

.task-config-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.task-card-header {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

/* 任务配置表单项样式优化 */
.task-config-card .el-form-item {
  margin-bottom: 10px;
}

.task-config-card .el-form-item:last-child {
  margin-bottom: 0;
}

/* 响应式布局 */
/* 中等屏幕：表格中状态显示为圆点，操作按钮只显示图标 */
@media (max-width: 980px) {
  .el-table .status-tag {
    display: none;
  }

  .el-table .status-dot {
    display: inline-block;
  }

  /* 隐藏按钮文字，显示图标（只针对操作列按钮） */
  .el-table .action-button .button-text {
    display: none;
  }

  .el-table .action-button .el-icon {
    display: inline-flex;
  }

  .el-table .action-button {
    padding: 8px;
    border-radius: 50%;
    width: 32px;
    height: 32px;
  }
}

@media (max-width: 600px) {
  .servers-page :deep(.el-dialog) {
    width: 95%;
  }
  
  .page-header {
    flex-direction: column;
    gap: 15px;
    align-items: stretch;
  }

  .page-header h1 {
    font-size: 20px;
    text-align: center;
  }

  .servers-page :deep(.el-table) {
    font-size: 12px;
  }

  .servers-page :deep(.el-table .el-table__cell) {
    padding: 8px 4px;
  }

  .servers-page :deep(.el-button) {
    font-size: 12px;
    padding: 6px 8px;
  }

  /* 任务配置卡片在平板及以下设备单列显示 */
  .task-config-card {
    flex: 1 1 100%;
    min-width: auto;
  }
}

@media (max-width: 480px) {
  .page-header h1 {
    font-size: 18px;
  }

  .servers-page :deep(.el-form-item__label) {
    font-size: 12px;
  }

  .servers-page :deep(.el-input__inner) {
    font-size: 12px;
  }

  .servers-page :deep(.el-button) {
    font-size: 11px;
    padding: 5px 6px;
  }

  /* 480px时select框内文字改为12px */
  .server-type-select :deep(.el-select__wrapper) {
    font-size: 12px;
  }
}

/* 库扫描任务样式 */
.scantask-header {
  display: flex;
  justify-content: center;
  margin-bottom: 10px;
}

.scantask-header .el-button {
  width: 100%;
}

.scantask-libraries {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scantask-library-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.library-inputs {
  flex: 1;
  display: flex;
  gap: 8px;
}

.library-select {
  flex: 2;
  min-width: 120px;
}

.crontab-input {
  flex: 1;
  min-width: 100px;
}

/* 移动端响应式布局 */
@media (max-width: 768px) {
  .library-inputs {
    flex-direction: column;
    gap: 6px;
  }

  .library-select,
  .crontab-input {
    width: 100%;
    min-width: 0;
  }

  .scantask-library-row {
    align-items: center;
  }
}

/* scantask卡片宽度设置 */
.task-config-card-wide {
  flex: 1 1 100%;
  min-width: 100%;
}
</style>