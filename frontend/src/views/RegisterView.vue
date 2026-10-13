<template>
  <div class="tm-auth-shell">
    <div class="tm-auth-card">
      <h1 class="tm-auth-brand">TravelMate</h1>
      <p class="tm-auth-subtitle">创建账号,开始规划你的旅行</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="Username" prop="username">
          <el-input
            v-model="form.username"
            placeholder="2-50 个字符"
            autocomplete="username"
            :prefix-icon="User"
          />
        </el-form-item>

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
            placeholder="至少 8 位"
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
          Register
        </el-button>
      </el-form>

      <div class="tm-auth-footer">
        已经有账号?
        <el-link type="primary" :underline="false" @click="goToLogin">返回登录</el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Lock, Message, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref(null)
const form = reactive({ username: '', email: '', password: '' })

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度需在 2-50 之间', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位', trigger: 'blur' },
  ],
}

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
    ElMessage.error(error.normalized?.message ?? '注册失败,请稍后重试')
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
