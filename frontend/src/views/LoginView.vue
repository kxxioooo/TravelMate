<template>
  <div class="tm-auth-shell">
    <div class="tm-auth-card">
      <h1 class="tm-auth-brand">TravelMate</h1>
      <p class="tm-auth-subtitle">登录后继续你的旅行计划</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="Email" prop="email">
          <el-input
            v-model="form.email"
            placeholder="you@example.com"
            autocomplete="email"
            :prefix-icon="Message"
          />
        </el-form-item>

        <el-form-item label="Password" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
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
          Login
        </el-button>
      </el-form>

      <div class="tm-auth-footer">
        还没有账号?
        <el-link type="primary" :underline="false" @click="goToRegister">立即注册</el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Lock, Message } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref(null)
const form = reactive({ email: '', password: '' })

const rules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

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
    ElMessage.error(error.normalized?.message ?? '登录失败,请稍后重试')
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
