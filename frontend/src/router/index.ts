import { createRouter, createWebHistory } from 'vue-router'
import { authApi } from '@/api/services'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/Login.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('../views/Dashboard.vue'),
      meta: { title: '仪表板', icon: 'DataBoard', requiresAuth: true }
    },
    {
      path: '/servers',
      name: 'Servers',
      component: () => import('../views/Servers.vue'),
      meta: { title: '服务器管理', icon: 'Monitor', requiresAuth: true }
    },
    {
      path: '/sync',
      name: 'Sync',
      component: () => import('../views/Sync.vue'),
      meta: { title: '同步管理', icon: 'RefreshRight', requiresAuth: true }
    },
    {
      path: '/logs',
      name: 'Logs',
      component: () => import('../views/Logs.vue'),
      meta: { title: '日志管理', icon: 'Document', requiresAuth: true }
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('../views/Settings.vue'),
      meta: { title: '系统设置', icon: 'Tools', requiresAuth: true }
    }
  ]
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  // 如果路由不需要认证，直接放行
  if (to.meta.requiresAuth === false) {
    next()
    return
  }

  // 检查登录状态
  try {
    const status = await authApi.getStatus()

    if (status.logged_in) {
      // 已登录，如果访问登录页则重定向到首页
      if (to.path === '/login') {
        next('/')
      } else {
        next()
      }
    } else {
      // 未登录，重定向到登录页
      if (to.path !== '/login') {
        next('/login')
      } else {
        next()
      }
    }
  } catch (error) {
    console.error('检查登录状态失败:', error)
    // 出错时默认重定向到登录页
    if (to.path !== '/login') {
      next('/login')
    } else {
      next()
    }
  }
})

export default router
