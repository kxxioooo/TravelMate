<template>
  <div class="tm-auth-shell">
    <!-- 未登录页没有顶部栏:语言切换固定到可视区域右上角(规格 §4.2) -->
    <LanguageSwitcher position="fixed" />

    <div class="tm-auth-card">
      <h1 class="tm-auth-brand">{{ t('app.name') }}</h1>
      <p class="tm-auth-subtitle">{{ t('auth.login_subtitle') }}</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="handleLogin"
      >
        <el-form-item :label="t('auth.email')" prop="email">
          <el-input
            v-model="form.email"
            :placeholder="t('auth.email_placeholder')"
            autocomplete="email"
            :prefix-icon="Message"
          />
        </el-form-item>

        <el-form-item :label="t('auth.password')" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="t('auth.password_placeholder')"
            autocomplete="current-password"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="tm-auth-submit"
          :loading="authStore.isLoading"
          @click="handleLogin"
        >
          {{ t('auth.login_button') }}
        </el-button>
      </el-form>

      <div class="tm-auth-footer">
        {{ t('auth.no_account') }}
        <el-link type="primary" underline="never" @click="goToRegister">
          {{ t('auth.go_register') }}
        </el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Lock, Message } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import LanguageSwitcher from '../components/common/LanguageSwitcher.vue'
import { formatLocalizedError } from '../utils/i18nDisplay'
import { useAuthStore } from '../stores/auth'

const { t } = useI18n()

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref(null)
const form = reactive({ email: '', password: '' })

/**
 * 校验规则用 computed:语言切换后 rule.message 立即重新求值,
 * 已显示过的错误文案也会跟着换语言。
 */
const rules = computed(() => ({
  email: [
    { required: true, message: t('auth.validation.email_required'), trigger: 'blur' },
    { type: 'email', message: t('auth.validation.email_invalid'), trigger: 'blur' },
  ],
  password: [{ required: true, message: t('auth.validation.password_required'), trigger: 'blur' }],
}))

/** 校验登录表单,只检查 email 与 password。 */
async function validateLoginForm() {
  if (!formRef.value) {
    return false
  }
  try {
    await formRef.value.validate()
    return true
  } catch {
    return false
  }
}

/** 校验 -> 登录 -> 根据 onboarding_completed 跳转。 */
async function handleLogin() {
  const valid = await validateLoginForm()
  if (!valid) {
    return
  }

  try {
    const user = await authStore.loginUser({ email: form.email, password: form.password })
    router.push(user.onboarding_completed ? { name: 'home' } : { name: 'onboarding' })
  } catch (error) {
    ElMessage.error(
      formatLocalizedError(error?.normalized ?? { status: 0 }, {
        t,
        fallbackKey: 'auth.login_failed',
      }),
    )
  }
}

/** 跳到注册页。 */
function goToRegister() {
  router.push({ name: 'register' })
}
</script>

<style scoped>
.tm-auth-submit {
  width: 100%;
  margin-top: 4px;
}
</style>
