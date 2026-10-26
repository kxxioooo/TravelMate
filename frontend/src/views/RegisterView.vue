<template>
  <div class="tm-auth-shell">
    <!-- 未登录页:语言切换固定在右上角 -->
    <LanguageSwitcher position="fixed" />

    <div class="tm-auth-card">
      <h1 class="tm-auth-brand">{{ t('app.name') }}</h1>
      <p class="tm-auth-subtitle">{{ t('auth.register_subtitle') }}</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="handleRegister"
      >
        <el-form-item :label="t('auth.username')" prop="username">
          <el-input
            v-model="form.username"
            :placeholder="t('auth.username_placeholder')"
            autocomplete="username"
            :prefix-icon="User"
          />
        </el-form-item>

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
            :placeholder="t('auth.password_placeholder_new')"
            autocomplete="new-password"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="handleRegister"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="tm-auth-submit"
          :loading="authStore.isLoading"
          @click="handleRegister"
        >
          {{ t('auth.register_button') }}
        </el-button>
      </el-form>

      <div class="tm-auth-footer">
        {{ t('auth.have_account') }}
        <el-link type="primary" underline="never" @click="goToLogin">
          {{ t('auth.go_login') }}
        </el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Lock, Message, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import LanguageSwitcher from '../components/common/LanguageSwitcher.vue'
import { useAuthStore } from '../stores/auth'
import { formatLocalizedError } from '../utils/i18nDisplay'

const { t } = useI18n()

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref(null)
const form = reactive({ username: '', email: '', password: '' })

/** 校验规则随语言实时重算。 */
const rules = computed(() => ({
  username: [
    { required: true, message: t('auth.validation.username_required'), trigger: 'blur' },
    { min: 2, max: 50, message: t('auth.validation.username_length'), trigger: 'blur' },
  ],
  email: [
    { required: true, message: t('auth.validation.email_required'), trigger: 'blur' },
    { type: 'email', message: t('auth.validation.email_invalid'), trigger: 'blur' },
  ],
  password: [
    { required: true, message: t('auth.validation.password_required'), trigger: 'blur' },
    { min: 8, message: t('auth.validation.password_length'), trigger: 'blur' },
  ],
}))

/** 校验注册表单:username / email / password。 */
async function validateRegisterForm() {
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

/** 校验 -> 注册 -> 进 Onboarding。 */
async function handleRegister() {
  const valid = await validateRegisterForm()
  if (!valid) {
    return
  }

  try {
    await authStore.registerUser({
      username: form.username,
      email: form.email,
      password: form.password,
    })
    router.push({ name: 'onboarding' })
  } catch (error) {
    ElMessage.error(
      formatLocalizedError(error?.normalized ?? { status: 0 }, {
        t,
        fallbackKey: 'auth.register_failed',
      }),
    )
  }
}

/** 回到登录页。 */
function goToLogin() {
  router.push({ name: 'login' })
}
</script>

<style scoped>
.tm-auth-submit {
  width: 100%;
  margin-top: 4px;
}
</style>
