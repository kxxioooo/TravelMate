import { ElMessage } from 'element-plus'
import { defineStore } from 'pinia'

import {
  createConversation,
  getConversation,
  listConversations,
  updateConversationCities,
} from '../api/conversations'
import { toErrorInfo } from '../api/http'
import { translate } from '../i18n'
import { formatLocalizedError } from '../utils/i18nDisplay'
import { useChatStore } from './chat'

/**
 * 读取统一的失败文案。
 *
 * v0.3.1:错误按"error_code 映射 > 后端 detail > 状态码 > 场景兜底 key"解析,
 * 且每次弹提示时用**当时**的语言翻译(不缓存已经翻译好的句子)。
 */
function resolveErrorMessage(error, fallbackKey) {
  return formatLocalizedError(toErrorInfo(error), { fallbackKey })
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
    /** 正在保存会话城市:期间禁止同会话重复提交与发送(任务书 §3.4)。 */
    isSavingCities: false,
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
        ElMessage.error(resolveErrorMessage(error, 'conversation.list_load_failed'))
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
          ElMessage.error(translate('conversation.create_invalid'))
          return null
        }

        this.items = [conversation, ...this.items.filter((item) => item.id !== conversation.id)]
        this.activeConversation = conversation
        useChatStore().clearChatState()

        return conversation
      } catch (error) {
        ElMessage.error(resolveErrorMessage(error, 'conversation.create_failed'))
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
          ElMessage.error(translate('conversation.detail_invalid'))
          return null
        }

        this.setActiveConversation(conversation)
        this.items = this.items.map((item) => (item.id === conversation.id ? conversation : item))
        await useChatStore().loadMessages(conversation.id)

        return conversation
      } catch (error) {
        ElMessage.error(resolveErrorMessage(error, 'conversation.open_failed'))
        return null
      } finally {
        this.isLoading = false
      }
    },

    /**
     * §18.4 / 任务书 §3.4 修改**指定会话**的绑定城市。
     *
     * 关键约束(来自任务书,都是踩过的坑):
     * - 必须按会话 ID 更新:编辑的可能是抽屉里非当前会话,迟到响应绝不能改写别的会话;
     * - 乐观更新只动这一条,响应只在 ID 匹配时落地,否则视为失败并回滚;
     * - 失败一律回滚并弹错,**不以乐观状态冒充成功**;
     * - 保存期间置 isSavingCities,由界面禁止同会话并发提交 / 发送。
     */
    async updateCities(conversationId, cities = []) {
      const targetId = conversationId ?? this.activeConversation?.id

      if (targetId === null || targetId === undefined || targetId === '') {
        return null
      }

      const previousTarget = this.items.find((item) => item.id === targetId) ?? null
      const previousActiveCities =
        this.activeConversation?.id === targetId ? this.activeConversation.cities : null
      const normalized = normalizeCities(cities)

      const restore = () => {
        if (previousTarget) {
          this.items = this.items.map((item) => (item.id === targetId ? previousTarget : item))
        }
        if (this.activeConversation?.id === targetId && previousActiveCities) {
          this.activeConversation = { ...this.activeConversation, cities: previousActiveCities }
        }
      }

      // 乐观更新:只动这一个会话,以及恰好是它的 active
      this.items = this.items.map((item) =>
        item.id === targetId ? { ...item, cities: normalized } : item,
      )
      if (this.activeConversation?.id === targetId) {
        this.activeConversation = { ...this.activeConversation, cities: normalized }
      }
      this.isSavingCities = true

      try {
        const data = await updateConversationCities(targetId, normalized)
        const conversation = normalizeConversation(data)

        // 响应无效或不是本次编辑的那个会话:不采信,回滚
        if (!conversation || conversation.id !== targetId) {
          restore()
          ElMessage.error(translate('conversation.update_cities_invalid'))
          return null
        }

        this.items = this.items.map((item) => (item.id === conversation.id ? conversation : item))
        if (this.activeConversation?.id === conversation.id) {
          this.activeConversation = conversation
        }

        return conversation
      } catch (error) {
        ElMessage.error(resolveErrorMessage(error, 'conversation.update_cities_failed'))
        restore()
        return null
      } finally {
        this.isSavingCities = false
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
      this.isSavingCities = false
    },
  },
})
