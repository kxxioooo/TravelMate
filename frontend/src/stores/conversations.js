import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'

import {
  createConversation,
  getConversation,
  listConversations,
  updateConversationCities,
} from '../api/conversations'
import { useChatStore } from './chat'

/**
 * 读取统一的失败文案(api/http.js 的拦截器已经把 detail 归一化)。
 */
function resolveErrorMessage(error, fallback) {
  return error?.normalized?.message ?? error?.message ?? fallback
}

/**
 * 城市数组归一化:只保留 city_name + adcode,并按 adcode 去重(§12 UNIQUE)。
 *
 * §40:这里的城市属于 Conversation,与 cityStore.selectedCity 完全是两套状态。
 */
function normalizeCities(cities) {
  if (!Array.isArray(cities)) {
    return []
  }

  const seen = new Set()
  const result = []

  for (const city of cities) {
    const cityName = String(city?.city_name ?? '').trim()
    if (!cityName) {
      continue
    }

    const adcode = city?.adcode === null || city?.adcode === undefined ? '' : String(city.adcode)
    const key = adcode || cityName
    if (seen.has(key)) {
      continue
    }

    seen.add(key)
    result.push({ city_name: cityName, adcode })
  }

  return result
}

/** 后端一条 Conversation -> 前端稳定结构。 */
function normalizeConversation(item) {
  if (!item || item.id === null || item.id === undefined) {
    return null
  }

  return {
    id: item.id,
    // 后端的 build_conversation_title() 是权威 title,这里原样保留,
    // 只有 Drawer 展示时才会用 fallbackConversationTitle() 兜底(§26.3)。
    title: typeof item.title === 'string' ? item.title : '',
    cities: normalizeCities(item.cities),
    created_at: item.created_at ?? null,
    updated_at: item.updated_at ?? null,
  }
}

/**
 * Conversation 状态中心(§18)。
 *
 * 消息历史刻意不放在这里 —— 它属于 chat store,切换会话时必须先清空,
 * 保证 A 的消息永远不会出现在 B(§5.2)。
 */
export const useConversationStore = defineStore('conversations', {
  state: () => ({
    items: [],
    activeConversation: null,
    drawerVisible: false,
    isLoading: false,
  }),

  actions: {
    /** §18.1 拉取当前用户的全部会话(后端已按 updated_at DESC 排序)。 */
    async loadConversations() {
      this.isLoading = true

      try {
        const data = await listConversations()
        this.items = (Array.isArray(data) ? data : [])
          .map((item) => normalizeConversation(item))
          .filter(Boolean)
        return this.items
      } catch (error) {
        // 拿不到列表时宁可为空,也不留下上一个账号/上一次请求的残影。
        this.items = []
        ElMessage.error(resolveErrorMessage(error, '会话列表加载失败'))
        return []
      } finally {
        this.isLoading = false
      }
    },

    /**
     * §18.2 新建会话。
     *
     * 允许 cities=[];新会话置顶并立即成为 active,同时清空聊天状态,
     * 保证新会话不会继承上一个会话的消息。
     */
    async createNewConversation(cities = []) {
      this.isLoading = true

      try {
        const data = await createConversation(normalizeCities(cities))
        const conversation = normalizeConversation(data)

        if (!conversation) {
          ElMessage.error('创建会话返回数据异常,请稍后重试')
          return null
        }

        this.items = [conversation, ...this.items.filter((item) => item.id !== conversation.id)]
        this.activeConversation = conversation
        useChatStore().clearChatState()

        return conversation
      } catch (error) {
        ElMessage.error(resolveErrorMessage(error, '创建会话失败,请稍后重试'))
        return null
      } finally {
        this.isLoading = false
      }
    },

    /**
     * §18.3 打开一个会话:先切换 active,再交给 chat store 拉消息。
     *
     * chatStore.loadMessages() 内部会先把 messages 置空,这是会话隔离的
     * 前端第一道保障(§5.2)。
     */
    async openConversation(id) {
      if (id === null || id === undefined || id === '') {
        return null
      }

      this.isLoading = true

      try {
        const data = await getConversation(id)
        const conversation = normalizeConversation(data)

        if (!conversation) {
          ElMessage.error('会话详情返回数据异常,请稍后重试')
          return null
        }

        this.setActiveConversation(conversation)
        this.items = this.items.map((item) => (item.id === conversation.id ? conversation : item))
        await useChatStore().loadMessages(conversation.id)

        return conversation
      } catch (error) {
        ElMessage.error(resolveErrorMessage(error, '会话打开失败,请稍后重试'))
        return null
      } finally {
        this.isLoading = false
      }
    },

    /**
     * §18.4 修改当前会话的绑定城市。
     *
     * 先本地乐观更新,再用后端返回值覆盖 —— 这样点击确认后
     * `.tm-conversation-cities` 会立即刷新,不会等一个网络往返。
     * 这里绝不触碰 cityStore:页面浏览城市由用户自己控制(§40)。
     */
    async updateCities(cities = []) {
      const active = this.activeConversation
      if (!active) {
        return null
      }

      const normalized = normalizeCities(cities)
      this.activeConversation = { ...active, cities: normalized }
      this.isLoading = true

      try {
        const data = await updateConversationCities(active.id, normalized)
        const conversation = normalizeConversation(data)

        if (!conversation) {
          return this.activeConversation
        }

        this.activeConversation = conversation
        this.items = this.items.map((item) => (item.id === conversation.id ? conversation : item))

        return conversation
      } catch (error) {
        ElMessage.error(resolveErrorMessage(error, '会话城市更新失败,请稍后重试'))
        // 回滚到修改前的城市,避免界面显示一个后端并不认可的状态。
        this.activeConversation = active
        return null
      } finally {
        this.isLoading = false
      }
    },

    /** §18.5 只修改 active,不发任何请求。 */
    setActiveConversation(conversation) {
      this.activeConversation = conversation ?? null
    },

    /** §18.6 关闭 AI 区内部的 Conversation Drawer。 */
    closeConversationDrawer() {
      this.drawerVisible = false
    },

    /** §18.7 退出登录 / 切换账号时清空,防止串用户。 */
    resetConversations() {
      this.items = []
      this.activeConversation = null
      this.drawerVisible = false
      this.isLoading = false
    },
  },
})
