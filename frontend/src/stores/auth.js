import { defineStore } from 'pinia'

import { getCurrentUser, login, logout, register } from '../api/auth'

/**
 * 认证状态中心。
 *
 * 前端不保存 JWT —— 凭证只在 HttpOnly Cookie 里,
 * 这里保存的只是"当前用户是谁 + 是否已完成 onboarding"。
 */
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    isAuthenticated: false,
    isBootstrapped: false,
    isLoading: false,
  }),

  actions: {
    /** 注册并立即建立登录态。 */
    async registerUser(form) {
      this.isLoading = true
      try {
        const data = await register(form)
        this.user = data.user
        this.isAuthenticated = true
        this.isBootstrapped = true
        return data.user
      } finally {
        this.isLoading = false
      }
    },

    /** 登录并更新 user / isAuthenticated。 */
    async loginUser(form) {
      this.isLoading = true
      try {
        const data = await login(form)
        this.user = data.user
        this.isAuthenticated = true
        this.isBootstrapped = true
        return data.user
      } finally {
        this.isLoading = false
      }
    },

    /** 退出:即使后端不可用,本地也一定清干净。 */
    async logoutUser() {
      try {
        await logout()
      } catch {
        // 忽略:本地退出优先
      } finally {
        this.resetAuthState()
        this.isBootstrapped = true
      }
    },

    /** 刷新页面时调用 /auth/me 恢复登录态;401 视为匿名。 */
    async restoreSession() {
      try {
        const user = await getCurrentUser()
        this.user = user
        this.isAuthenticated = true
      } catch {
        this.resetAuthState()
      } finally {
        this.isBootstrapped = true
      }
      return this.user
    },

    /** Onboarding 完成后立即同步,避免守卫把用户又弹回 /onboarding。 */
    setOnboardingCompleted(value) {
      if (this.user) {
        this.user.onboarding_completed = Boolean(value)
      }
    },

    /** 统一清理登录状态。 */
    resetAuthState() {
      this.user = null
      this.isAuthenticated = false
    },
  },
})
