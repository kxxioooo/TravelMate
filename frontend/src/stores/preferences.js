import { defineStore } from 'pinia'

import { getMyPreferences, saveMyPreferences, skipOnboarding } from '../api/preferences'

/** 偏好状态中心:当前用户唯一的一份偏好。 */
export const usePreferencesStore = defineStore('preferences', {
  state: () => ({
    preferences: null,
    isLoaded: false,
    isSaving: false,
  }),

  actions: {
    /** 读取当前用户偏好(没保存过会拿到空结构)。 */
    async loadPreferences() {
      const data = await getMyPreferences()
      this.preferences = data
      this.isLoaded = true
      return data
    },

    /** 保存偏好。 */
    async savePreferences(data) {
      this.isSaving = true
      try {
        this.preferences = await saveMyPreferences(data)
        this.isLoaded = true
        return this.preferences
      } finally {
        this.isSaving = false
      }
    },

    /** 跳过 Onboarding,返回更新后的用户信息。 */
    async skipPreferences() {
      this.isSaving = true
      try {
        return await skipOnboarding()
      } finally {
        this.isSaving = false
      }
    },

    /** 退出登录时清空,避免下一个账号看到上一个人的偏好。 */
    resetPreferences() {
      this.preferences = null
      this.isLoaded = false
    },
  },
})
