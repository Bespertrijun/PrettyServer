<template>
  <div class="settings-page">
    <div class="page-header">
      <h1>环境设置</h1>
    </div>

    <el-row :gutter="20">
      <!-- 修改密码卡片 -->
      <el-col :span="24" class="settings-card">
        <el-card>
          <template #header>
            <h3>账户安全</h3>
          </template>
          <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="150px">
            <el-form-item label="旧密码" prop="oldPassword">
              <el-input
                v-model="passwordForm.oldPassword"
                type="password"
                show-password
                placeholder="请输入旧密码"
                style="max-width: 400px;"
              />
            </el-form-item>
            <el-form-item label="新密码" prop="newPassword">
              <el-input
                v-model="passwordForm.newPassword"
                type="password"
                show-password
                placeholder="请输入新密码"
                style="max-width: 400px;"
              />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirmPassword">
              <el-input
                v-model="passwordForm.confirmPassword"
                type="password"
                show-password
                placeholder="请再次输入新密码"
                style="max-width: 400px;"
              />
            </el-form-item>
            <el-form-item class="button-form-item">
              <div class="button-group">
                <el-button type="primary" @click="changePassword" :loading="changingPassword">
                  <el-icon><Lock /></el-icon>
                  修改密码
                </el-button>
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 双因素认证配置卡片 -->
      <el-col :span="24" class="settings-card">
        <el-card>
          <template #header>
            <h3>@2FA配置</h3>
          </template>
          <div v-if="!twoFAEnabled" class="twofa-content">
            <el-alert
              title="未配置2FA"
              type="warning"
              description="您尚未配置2FA。启用后，您需要使用认证器 APP（如 Google Authenticator、Microsoft Authenticator）扫描二维码绑定账户。"
              :closable="false"
              style="margin-bottom: 20px;"
            />
            <div class="twofa-button-group">
              <el-button type="primary" @click="enable2FA" :loading="enabling2FA">
                <el-icon><Lock /></el-icon>
                配置@2FA
              </el-button>
            </div>
          </div>
          <div v-else class="twofa-content">
            <el-alert
              title="已启用2FA"
              type="success"
              description="您的账户已启用2FA，登录时需要输入验证码。"
              :closable="false"
              style="margin-bottom: 20px;"
            />
            <div class="twofa-button-group">
              <el-button type="danger" @click="showDisable2FADialog">
                <el-icon><Lock /></el-icon>
                禁用@2FA
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 环境配置卡片 -->
      <el-col :span="24" class="settings-card">
        <el-card v-loading="loading">
          <template #header>
            <h3>环境配置</h3>
          </template>
          <el-form v-if="envConfig" :model="envConfig" label-width="150px">
            <el-form-item label="TMDB API Key" required>
              <el-input v-model="envConfig.tmdb_api" placeholder="请输入 TMDB API Key" />
              <div class="form-tip">用于获取中文演员信息和 Emby 季标题</div>
            </el-form-item>
            <el-form-item label="并发数" required>
              <el-input-number v-model="envConfig.concurrent_num" :min="1" :max="10000" />
            </el-form-item>
            <div class="form-tip" style="margin-top: -16px; margin-bottom: 18px; margin-left: 150px;">
              协程并发数，越大越快，但会占用更多系统资源
            </div>
            <el-form-item label="启用代理">
              <el-switch v-model="envConfig.proxy.isproxy" />
            </el-form-item>
            <div class="form-tip" style="margin-top: -16px; margin-bottom: 18px; margin-left: 150px;">
              仅访问 TMDB 代理（适用于国内环境）
            </div>
            <el-form-item label="代理地址" v-if="envConfig.proxy.isproxy">
              <el-input v-model="envConfig.proxy.http" placeholder="http://user:pass@ip:port" />
              <div class="form-tip">仅支持 HTTP 代理，格式: http://user:pass@ip:port 或 http://ip:port</div>
            </el-form-item>
            <el-form-item class="button-form-item">
              <div class="button-group">
                <el-button type="primary" @click="saveConfig" :loading="saving">
                  <el-icon><Check /></el-icon>
                  保存配置
                </el-button>
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 2FA 绑定对话框 -->
    <el-dialog
      v-model="twoFADialogVisible"
      title="配置@2FA"
      width="500px"
      :close-on-click-modal="false"
    >
      <div v-if="qrCodeData" style="text-align: center;">
        <p style="margin-bottom: 15px;">请使用认证器 APP 扫描以下二维码：</p>
        <img :src="qrCodeData" alt="QR Code" style="max-width: 250px; margin: 20px auto;" />
        <p style="margin-top: 15px; font-size: 12px; color: #666;">
          密钥：<code style="background: #f5f5f5; padding: 2px 6px;">{{ secretKey }}</code>
        </p>
        <el-divider />
        <el-form :model="verifyForm" style="margin-top: 20px;">
          <el-form-item label="验证码" label-width="80px">
            <el-input
              v-model="verifyForm.code"
              placeholder="请输入 6 位验证码"
              maxlength="6"
              style="width: 200px;"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="twoFADialogVisible = false">取消</el-button>
        <el-button type="primary" @click="verify2FA" :loading="verifying2FA">
          验证并启用
        </el-button>
      </template>
    </el-dialog>

    <!-- 禁用 2FA 对话框 -->
    <el-dialog
      v-model="disable2FADialogVisible"
      title="禁用双因素认证"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form :model="disable2FAForm">
        <el-form-item label="密码确认" label-width="100px">
          <el-input
            v-model="disable2FAForm.password"
            type="password"
            show-password
            placeholder="请输入密码以确认操作"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="disable2FADialogVisible = false">取消</el-button>
        <el-button type="danger" @click="disable2FA" :loading="disabling2FA">
          确认禁用
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { Check, Lock } from '@element-plus/icons-vue'
import { configApi, authApi } from '@/api/services'
import type { EnvConfig } from '@/api/types'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { encryptPassword } from '@/utils/crypto'

const envConfig = ref<EnvConfig>()

const loading = ref(false)
const saving = ref(false)

// 修改密码表单
const passwordFormRef = ref<FormInstance>()
const changingPassword = ref(false)
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 密码表单验证规则
const validateConfirmPassword = (rule: any, value: any, callback: any) => {
  if (value === '') {
    callback(new Error('请再次输入新密码'))
  } else if (value !== passwordForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules: FormRules = {
  oldPassword: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少8位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

// 2FA相关
const twoFAEnabled = computed(() => {
  return envConfig.value?.use_2fa === true
})
const enabling2FA = ref(false)
const verifying2FA = ref(false)
const disabling2FA = ref(false)
const twoFADialogVisible = ref(false)
const disable2FADialogVisible = ref(false)
const qrCodeData = ref('')
const secretKey = ref('')
const verifyForm = reactive({
  code: ''
})
const disable2FAForm = reactive({
  password: ''
})

const loadConfig = async () => {
  loading.value = true
  try {
    const configData = await configApi.getConfig()
    envConfig.value = configData
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  if (!envConfig.value) return

  saving.value = true
  try {
    await configApi.updateConfig(envConfig.value)
    ElMessage.success('配置保存成功')
  } catch (error) {
    console.error('保存配置失败:', error)
    ElMessage.error('配置保存失败，请检查日志')
  } finally {
    saving.value = false
  }
}

const changePassword = async () => {
  if (!passwordFormRef.value) return

  await passwordFormRef.value.validate(async (valid) => {
    if (!valid) return

    changingPassword.value = true
    try {
      // 使用 ECC 加密旧密码和新密码
      const encryptedOldPassword = await encryptPassword(passwordForm.oldPassword)
      const encryptedNewPassword = await encryptPassword(passwordForm.newPassword)

      const result = await authApi.changePassword({
        old_password: encryptedOldPassword,
        new_password: encryptedNewPassword
      })

      if (result.status === 'success') {
        ElMessage.success('密码修改成功')
        // 重置表单
        passwordForm.oldPassword = ''
        passwordForm.newPassword = ''
        passwordForm.confirmPassword = ''
        passwordFormRef.value?.resetFields()
      } else {
        ElMessage.error(result.message || '密码修改失败，请检查日志')
      }
    } catch (error: any) {
      console.error('修改密码失败:', error)
      ElMessage.error('修改密码失败，请检查日志')
    } finally {
      changingPassword.value = false
    }
  })
}

const enable2FA = async () => {
  enabling2FA.value = true
  try {
    const result = await authApi.enable2FA()
    qrCodeData.value = result.qr_code
    secretKey.value = result.secret
    twoFADialogVisible.value = true
    ElMessage.success(result.message)
  } catch (error: any) {
    console.error('启用 2FA 失败:', error)
    ElMessage.error('启用 2FA 失败，请检查日志')
  } finally {
    enabling2FA.value = false
  }
}

const verify2FA = async () => {
  if (!verifyForm.code) {
    ElMessage.warning('请输入验证码')
    return
  }

  verifying2FA.value = true
  try {
    const result = await authApi.verify2FA(verifyForm.code)
    if (result.status === 'success') {
      ElMessage.success('双因素认证配置成功')
      twoFADialogVisible.value = false
      verifyForm.code = ''
      qrCodeData.value = ''
      secretKey.value = ''

      await loadConfig()
    } else {
      ElMessage.error(result.message || '验证失败')
    }
  } catch (error: any) {
    console.error('验证 2FA 失败:', error)
    ElMessage.error('验证失败，请检查验证码是否正确')
  } finally {
    verifying2FA.value = false
  }
}

const showDisable2FADialog = () => {
  disable2FAForm.password = ''
  disable2FADialogVisible.value = true
}

const disable2FA = async () => {
  if (!disable2FAForm.password) {
    ElMessage.warning('请输入密码')
    return
  }

  disabling2FA.value = true
  try {
    const result = await authApi.disable2FA(disable2FAForm.password)
    if (result.status === 'success') {
      ElMessage.success('双因素认证已禁用')
      disable2FADialogVisible.value = false
      disable2FAForm.password = ''

      await loadConfig()
    } else {
      ElMessage.error(result.message || '禁用失败')
    }
  } catch (error: any) {
    console.error('禁用 2FA 失败:', error)
    ElMessage.error('禁用失败，请检查密码是否正确')
  } finally {
    disabling2FA.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.settings-page {
  max-width: 1200px;
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

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.5;
}

.button-form-item {
  margin-left: -150px;
}

.button-form-item .button-group {
  display: flex;
  justify-content: flex-end;
  width: 100%;
}

.settings-card {
  margin-bottom: 20px;
}

.settings-card:last-child {
  margin-bottom: 0;
}

.twofa-content {
  position: relative;
  min-height: 100px;
}

.twofa-button-group {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>