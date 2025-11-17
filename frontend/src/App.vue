<template>
  <!-- 登录页面：无布局 -->
  <div v-if="isLoginPage" class="login-wrapper">
    <RouterView />
  </div>

  <!-- 主应用布局 -->
  <el-container v-else class="app-container">
    <!-- 移动端遮罩层 -->
    <div
      v-if="isMobileMenuOpen"
      class="mobile-overlay"
      @click="closeMobileMenu"
    ></div>

    <el-aside
      width="250px"
      class="sidebar"
      :class="{ 'mobile-open': isMobileMenuOpen }"
    >
      <div class="logo-container">
        <h2 class="logo-title">PrettyServer</h2>
        <p class="logo-subtitle">媒体服务器管理工具</p>
      </div>

      <el-menu
        :default-active="$route.name"
        class="sidebar-menu"
        router
        :unique-opened="true"
        @select="handleMenuSelect"
      >
        <el-menu-item
          v-for="route in menuRoutes"
          :key="route.name"
          :index="route.path"
        >
          <el-icon>
            <component :is="route.meta.icon" />
          </el-icon>
          <span>{{ route.meta.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-content">
          <div class="header-left">
            <!-- 移动端菜单按钮 -->
            <el-button
              :icon="Menu"
              circle
              class="mobile-menu-btn"
              @click="toggleMobileMenu"
            />

            <el-breadcrumb separator="/" class="breadcrumb">
              <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
              <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>

          <div class="header-actions">
            <el-tooltip content="系统状态">
              <el-badge :value="serverCount" class="status-badge">
                <el-button :icon="Monitor" circle />
              </el-badge>
            </el-tooltip>

            <!-- 用户信息下拉菜单 -->
            <el-dropdown trigger="click" class="user-dropdown">
              <div class="user-info">
                <el-avatar :size="32" :icon="User" class="user-avatar" />
                <span class="user-name">{{ userInfo.name }}</span>
                <el-icon class="dropdown-icon">
                  <ArrowDown />
                </el-icon>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item>
                    <el-icon><User /></el-icon>
                    个人资料
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="handleLogout">
                    <el-icon><SwitchButton /></el-icon>
                    退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </el-header>

      <el-main class="main-content">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Monitor, Menu, User, ArrowDown, SwitchButton } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemApi, authApi } from '@/api/services'

const route = useRoute()
const router = useRouter()

// 判断是否为登录页面
const isLoginPage = computed(() => route.path === '/login')

// 服务器数量
const serverCount = ref(0)

// 移动端菜单状态
const isMobileMenuOpen = ref(false)

// 用户信息
const userInfo = ref({
  name: 'Admin',
  avatar: '',
  role: '管理员'
})

// 菜单路由
const menuRoutes = computed(() => {
  return router.getRoutes().filter(route =>
    route.meta?.title && route.path !== '/'
  )
})

// 当前页面标题
const currentPageTitle = computed(() => {
  return route.meta?.title || '未知页面'
})

// 切换移动端菜单
const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

// 关闭移动端菜单
const closeMobileMenu = () => {
  isMobileMenuOpen.value = false
}

// 菜单选择处理（移动端选择后自动关闭菜单）
const handleMenuSelect = () => {
  if (window.innerWidth <= 768) {
    closeMobileMenu()
  }
}

// 监听窗口大小变化
const handleResize = () => {
  if (window.innerWidth > 768 && isMobileMenuOpen.value) {
    closeMobileMenu()
  }
}

// 获取服务器数量
const fetchServerCount = async () => {
  try {
    const status = await systemApi.getStatus()
    serverCount.value = status.servers_count
  } catch (error) {
    console.error('获取系统状态失败:', error)
    // 后端未启动时显示默认值
    serverCount.value = 0
  }
}

// 退出登录
const handleLogout = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要退出登录吗？',
      '退出确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    // 调用登出 API
    await authApi.logout()
    ElMessage.success('已退出登录')

    // 跳转到登录页
    router.push('/login')
  } catch (error: any) {
    // 用户点击取消
    if (error !== 'cancel') {
      console.error('退出登录失败:', error)
      ElMessage.error('退出登录失败，请检查日志')
    }
  }
}

// 组件挂载后初始化
onMounted(() => {
  fetchServerCount()
  window.addEventListener('resize', handleResize)
})

// 组件卸载时清理
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
/* 登录页面包装器 */
.login-wrapper {
  width: 100%;
  height: 100vh;
}

.app-container {
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  background-color: var(--el-menu-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  overflow-y: auto;
}

.logo-container {
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid var(--el-border-color-light);
  margin-bottom: 20px;
}

.logo-title {
  margin: 0;
  color: var(--el-color-primary);
  font-size: 22px;
  font-weight: bold;
}

.logo-subtitle {
  margin: 5px 0 0 0;
  color: var(--el-text-color-regular);
  font-size: 11px;
}

.sidebar-menu {
  border: none;
}

.header {
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.mobile-menu-btn {
  display: none;
}

.breadcrumb {
  flex: 1;
}

/* 移动端遮罩层 */
.mobile-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 999;
  display: none;
}

.status-badge {
  margin-right: 8px;
}

/* 用户信息样式 */
.user-dropdown {
  margin-left: 15px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: var(--el-fill-color-light);
}

.user-avatar {
  background-color: var(--el-color-primary);
}

.user-name {
  font-size: 14px;
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.dropdown-icon {
  font-size: 12px;
  color: var(--el-text-color-regular);
  transition: transform 0.3s;
}

.user-dropdown.is-active .dropdown-icon {
  transform: rotate(180deg);
}

.main-content {
  background-color: var(--el-bg-color-page);
  padding: 20px;
  overflow-y: auto;
  height: calc(100vh - 60px);
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .app-container :deep(.el-aside) {
    width: 200px !important;
  }

  .logo-title {
    font-size: 18px;
  }

  .logo-subtitle {
    font-size: 10px;
  }
}

@media (max-width: 992px) {
  .app-container :deep(.el-aside) {
    width: 180px !important;
  }

  .main-content {
    padding: 15px;
  }

  .header-content {
    gap: 10px;
    height: auto;
    padding: 10px 0;
  }

  .header {
    height: auto;
    padding: 10px 15px;
  }

  .main-content {
    height: calc(100vh - 80px);
  }
}

@media (max-width: 768px) {
  .app-container :deep(.el-aside) {
    position: fixed;
    left: -250px;
    top: 0;
    height: 100vh;
    z-index: 1000;
    transition: left 0.3s ease;
    width: 250px !important;
  }

  .app-container :deep(.el-aside.mobile-open) {
    left: 0;
  }

  .mobile-overlay {
    display: block !important;
  }

  .mobile-menu-btn {
    display: inline-flex !important;
  }

  .main-content {
    margin-left: 0;
    padding: 10px;
    height: calc(100vh - 60px);
  }

  .header {
    padding: 0 15px;
    height: 60px;
  }

  .header-content {
    flex-direction: row;
    height: 60px;
    gap: 10px;
  }

  .header-left {
    flex: 1;
    gap: 10px;
  }

  .breadcrumb {
    flex: 1;
    min-width: 0;
  }

  .header-actions {
    gap: 8px;
  }

  .header-actions .el-button {
    padding: 8px;
  }

  /* 移动端用户信息调整 */
  .user-dropdown {
    margin-left: 8px;
  }

  .user-name {
    display: none;
  }

  .user-info {
    gap: 4px;
    padding: 3px 6px;
  }
}

@media (max-width: 480px) {
  .header-left {
    gap: 8px;
  }

  .header-actions {
    gap: 6px;
  }

  .header-actions .el-button {
    padding: 6px;
  }

  /* 小屏幕用户信息进一步调整 */
  .user-dropdown {
    margin-left: 6px;
  }

  .user-info {
    gap: 2px;
    padding: 2px 4px;
  }

  .user-avatar {
    width: 28px !important;
    height: 28px !important;
  }

  .main-content {
    padding: 8px;
    height: calc(100vh - 55px);
  }

  .header {
    height: 55px;
  }

  .header-content {
    height: 55px;
  }

  .breadcrumb :deep(.el-breadcrumb__item) {
    font-size: 12px;
  }

  .logo-title {
    font-size: 16px;
  }

  .logo-subtitle {
    font-size: 9px;
  }
}
</style>
