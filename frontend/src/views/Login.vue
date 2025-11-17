<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>PrettyServer</h2>
          <p>媒体服务器管理工具</p>
        </div>
      </template>

      <el-form :model="loginForm" :rules="rules" ref="loginFormRef" label-width="0">
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="用户名"
            size="large"
            clearable
            @keyup.enter="handleLogin"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item prop="totpCode">
          <el-input
            v-model="loginForm.totpCode"
            placeholder="2FA"
            size="large"
            maxlength="6"
            @keyup.enter="handleLogin"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            如果启用了双因素认证，请输入认证器 APP 中的 6 位验证码
          </div>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            style="width: 100%"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { authApi } from '@/api/services'
import { encryptPassword } from '@/utils/crypto'

const router = useRouter()
const loginFormRef = ref()
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
  totpCode: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    loading.value = true
    try {
      // 使用 ECC 加密密码
      const encryptedPassword = await encryptPassword(loginForm.password)

      const credentials: any = {
        username: loginForm.username,
        password: encryptedPassword
      }

      // 如果填写了验证码，一起发送
      if (loginForm.totpCode) {
        credentials.totp_code = loginForm.totpCode
      }

      const result = await authApi.login(credentials)

      if (result.status === 'success') {
        ElMessage.success('登录成功')
        // 跳转到首页
        router.push('/')
      } else if (result.status === 'require_2fa') {
        // 需要 2FA 验证码，但用户没有填写
        ElMessage.warning(result.message || '请输入2FA验证码')
      } else {
        ElMessage.error(result.message || '登录失败，请检查用户名和密码，请检查日志')
      }
    } catch (error: any) {
      console.error('登录失败:', error)
      ElMessage.error('登录失败: '+ error.message)
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
  max-width: 90%;
}

.card-header {
  text-align: center;
}

.card-header h2 {
  margin: 0;
  font-size: 28px;
  color: #303133;
}

.card-header p {
  margin: 8px 0 0 0;
  color: #909399;
  font-size: 14px;
}

:deep(.el-card__header) {
  padding: 30px 20px;
  border-bottom: 1px solid #f0f0f0;
}

:deep(.el-card__body) {
  padding: 30px;
}

:deep(.el-form-item) {
  margin-bottom: 24px;
}

:deep(.el-form-item:last-child) {
  margin-bottom: 0;
}
</style>
