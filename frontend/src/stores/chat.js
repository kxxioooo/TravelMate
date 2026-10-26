import { defineStore } from 'pinia'

import { getMessages, sendMessage } from '../api/chat'
import { toErrorInfo } from '../api/http'
import { buildLocalUserMessage, normalizeActivities } from '../utils/chat'

/**
 * 后端一条 message -> 前端稳定结构。
 *
 * 只保留 role / content / created_at,前端不展示任何内部字段(§43)。
 *
 * v0.3.1 关键约束:历史消息的 `content` **原样保存、原样渲染**。
 * 切换语言绝不翻译、不覆盖、不重新生成(规格 §8.2)。
 */
function normalizeMessage(item, fallbackId) {
  if (!item || typeof item !== 'object') {
    return null
  }

  const content = typeof item.content === 'string' ? item.content : ''
  if (!content) {
    return null
  }

  return {
    id: item.id ?? fallbackId,
    role: item.role === 'assistant' ? 'assistant' : 'user',
    content,
    created_at: item.created_at ?? null,
    pending: false,
    failed: false,
  }
}

/**
 * Chat 状态中心(§24)。
 *
 * `messages` 只属于"当前 active Conversation"。每次切换会话都会整体替换,
 * 并且用数组引用做流标记 —— 会话切换后,旧请求的结果会被直接丢弃,
 * 保证 A 的消息永远不会落到 B(§5.2 / §45)。
 */
export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    activities: [],
    draftPrompt: '',
    isSending: false,
    error: null,
  }),

  actions: {
    /**
     * §24.1 拉取某个会话的历史消息。
     *
     * 无论成功失败都先把 messages 置空,再替换 —— 绝不在切换会话时
     * 让上一条会话的消息短暂可见。历史 content 不翻译。
     */
    async loadMessages(conversationId) {
      if (conversationId === null || conversationId === undefined || conversationId === '') {
        this.messages = []
        this.activities = []
        this.error = null
        return []
      }

      this.messages = []
      this.activities = []
      this.error = null
      this.isSending = false

      try {
        const data = await getMessages(conversationId)
        this.messages = (Array.isArray(data) ? data : [])
          .map((item, index) => normalizeMessage(item, `message-${index}`))
          .filter(Boolean)
        return this.messages
      } catch (error) {
        this.messages = []
        this.error = toErrorInfo(error)
        return []
      }
    },

    /**
     * §24.2 发送一条用户消息,严格按 9 步走:
     * trim -> isSending -> 插入本地临时 user message -> 显示"正在理解请求……"
     * -> POST -> 用后端正式 user_message 替换临时项 -> append assistant_message
     * -> activities = 后端 activities -> isSending=false。
     *
     * 失败时保留用户输入(失败气泡可重试),并且绝不伪造 assistant 消息。
     */
    async sendUserMessage(conversationId, content) {
      // 1. trim
      const text = String(content ?? '').trim()
      if (!text || this.isSending) {
        return null
      }

      if (conversationId === null || conversationId === undefined || conversationId === '') {
        this.error = { status: 0, errorCode: '', key: 'chat.no_conversation_error', detail: '' }
        return null
      }

      this.error = null
      // 2. isSending = true
      this.isSending = true

      // 3. 先构造本地 user message 显示在 UI(重试时先移除同内容的失败项)
      this.messages = this.messages.filter((message) => !(message.failed && message.content === text))
      const localMessage = buildLocalUserMessage(text)
      this.messages = [...this.messages, localMessage]
      /**
       * 流标记:本函数之外只有 loadMessages() 会整体替换 messages
       * (也就是切换会话),一旦发生,旧请求的结果就会被丢弃(§5.2)。
       */
      let streamToken = this.messages

      // 4. 显示真实的等待状态(不是伪造的工具调用,只是本地 UI 状态)
      this.activities = [{ type: 'agent', status: 'running', code: 'agent.thinking', params: null, text: '' }]

      try {
        // 5. POST backend
        const data = await sendMessage(conversationId, text)

        if (this.messages !== streamToken) {
          return null
        }

        // 6. 用后端正式 user_message 替换临时项
        const officialUser =
          normalizeMessage(data?.user_message, localMessage.id) ?? { ...localMessage, pending: false }
        this.messages = this.messages.map((message) =>
          message.id === localMessage.id ? { ...officialUser, pending: false, failed: false } : message,
        )
        streamToken = this.messages

        // 7. append assistant_message(后端没给就不补,绝不伪造)
        const assistantMessage = normalizeMessage(
          data?.assistant_message,
          `assistant-${Date.now()}`,
        )
        if (assistantMessage) {
          this.messages = [...this.messages, assistantMessage]
          streamToken = this.messages
        }

        // 8. activities = 后端真实 activities;空数组就什么都不显示
        this.activities = normalizeActivities(data?.activities)

        return data
      } catch (error) {
        if (this.messages !== streamToken) {
          return null
        }

        // 失败:保留用户输入(标记为失败,可点击重试),不写伪成功消息
        this.error = toErrorInfo(error)
        this.messages = this.messages.map((message) =>
          message.id === localMessage.id ? { ...message, pending: false, failed: true } : message,
        )
        streamToken = this.messages
        this.activities = []

        return null
      } finally {
        // 9. isSending = false(若期间已切换会话,由 loadMessages 负责复位)
        if (this.messages === streamToken) {
          this.isSending = false
        }
      }
    },

    /** §24.3 Recommended Prompt 点击后填入输入框(不发送)。 */
    setDraftPrompt(prompt) {
      this.draftPrompt = String(prompt ?? '')
    },

    /** §24.4 发送后清空草稿。 */
    clearDraftPrompt() {
      this.draftPrompt = ''
    },

    /** §24.5 新建 / 切换 Conversation 时清空当前会话的聊天状态。 */
    clearChatState() {
      this.messages = []
      this.activities = []
      this.error = null
      this.isSending = false
    },

    /** §24.6 退出登录时完全清空(包括 draft,防止串到下一个账号)。 */
    resetChat() {
      this.clearChatState()
      this.draftPrompt = ''
    },
  },
})
