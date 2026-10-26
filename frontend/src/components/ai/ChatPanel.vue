<template>
  <section class="tm-chat-panel">
    <header class="tm-chat-header">
      <button
        type="button"
        class="tm-drawer-toggle"
        :aria-label="t('chat.open_conversations')"
        :title="t('chat.conversations_title')"
        @click="openConversationDrawer"
      >
        ☰
      </button>

      <div class="tm-chat-header-main">
        <h2 class="tm-chat-title">{{ t('chat.title') }}</h2>

        <div class="tm-chat-header-cities">
          <button
            type="button"
            class="tm-conversation-cities"
            :disabled="!hasActiveConversation"
            :title="hasActiveConversation ? t('chat.edit_cities_title') : t('chat.no_active_conversation')"
            @click="dialogs.mode = 'edit'"
          >
            {{ conversationCitiesText }}
          </button>

          <button
            type="button"
            class="tm-edit-cities-btn"
            :disabled="!hasActiveConversation"
            :title="t('chat.modify_cities_title')"
            @click="dialogs.mode = 'edit'"
          >
            {{ t('chat.edit_cities') }}
          </button>
        </div>
      </div>

      <el-button class="tm-new-chat-btn" type="primary" plain @click="openNewConversation">
        + {{ t('chat.new_chat') }}
      </el-button>
    </header>

    <div class="tm-chat-body">
      <!-- §25.1 没有 active Conversation 时显示欢迎态,不强制自动建会话 -->
      <div v-if="!hasActiveConversation" class="tm-chat-welcome">
        <h3 class="tm-chat-welcome-title">{{ t('chat.welcome_title') }}</h3>
        <p class="tm-chat-welcome-text">{{ t('chat.welcome_text') }}</p>
        <ul class="tm-chat-welcome-list">
          <li v-for="key in WELCOME_EXAMPLE_KEYS" :key="key">{{ t(key) }}</li>
        </ul>
      </div>

      <MessageList v-show="hasActiveConversation" :messages="chatStore.messages" @retry="handleSend" />
    </div>

    <p v-if="chatStore.error" class="tm-chat-error">{{ errorText }}</p>

    <!-- §25.5 只显示真实发生的活动;发送中先显示"正在理解请求……" -->
    <AgentActivity v-show="chatStore.activities.length" :activities="chatStore.activities" />

    <ChatInput
      :draft="chatStore.draftPrompt"
      :sending="chatStore.isSending"
      @send="handleSend"
    />

    <ConversationDrawer @new-chat="openNewConversation" />

    <!-- 同一个对话框承担"新建"与"改城市"两种模式,保证页面里只有一个对话框实例 -->
    <NewConversationDialog
      :model-value="dialogs.mode !== null"
      :mode="dialogs.mode ?? 'create'"
      :initial-cities="activeConversationCities"
      @update:model-value="dialogs.mode = null"
      @created="handleConversationSelected"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import { useI18n } from 'vue-i18n'

import { useChatStore } from '../../stores/chat'
import { useConversationStore } from '../../stores/conversations'
import { formatLocalizedError, displayCityName } from '../../utils/i18nDisplay'
import AgentActivity from './AgentActivity.vue'
import ChatInput from './ChatInput.vue'
import ConversationDrawer from './ConversationDrawer.vue'
import MessageList from './MessageList.vue'
import NewConversationDialog from './NewConversationDialog.vue'

/**
 * 欢迎态里的示例问题。
 *
 * 只存 i18n key —— 推荐问题属于应用控制的文案,必须随语言切换;
 * 点击 Recommended Prompts 才是真正的填充入口。
 */
const WELCOME_EXAMPLE_KEYS = [
  'chat.welcome_example_1',
  'chat.welcome_example_2',
  'chat.welcome_example_3',
]

const { t, locale } = useI18n()

const conversationStore = useConversationStore()
const chatStore = useChatStore()

/**
 * 本组件私有的弹窗状态。
 *
 * 用 reactive 对象而不是 ref:模板里的 `dialogs.mode = 'edit'` 是成员赋值,
 * 既保持响应式,也不涉及对 ref 本身的赋值。
 */
const dialogs = reactive({ mode: null })

const hasActiveConversation = computed(() => Boolean(conversationStore.activeConversation))

/** §40 这里读的是 Conversation 的城市,与 cityStore.selectedCity 完全无关。 */
const activeConversationCities = computed(() => conversationStore.activeConversation?.cities ?? [])

/** 会话城市:英文模式 `Chengdu (成都) · Leshan (乐山)`,城市集合不变。 */
const conversationCitiesText = computed(() => {
  if (!hasActiveConversation.value) {
    return t('conversation.no_conversation')
  }

  const names = activeConversationCities.value.map((city) => displayCityName(city, locale.value))

  return names.length ? names.join(' · ') : t('conversation.no_city')
})

/** 本地化错误文案(按 error_code / detail / 状态码解析,切换语言即时更新)。 */
const errorText = computed(() => formatLocalizedError(chatStore.error, { t }))

/**
 * §25.1 initializeChat():进入主页时拉会话列表。
 *
 * 有 active 就加载它的历史消息;没有就显示欢迎态(不强制自动建会话)。
 * 没有消息时才请求,避免主页与城市页布局切换时重复拉取。
 */
async function initializeChat() {
  await conversationStore.loadConversations()

  if (!conversationStore.activeConversation) {
    return
  }

  if (chatStore.messages.length) {
    return
  }

  await chatStore.loadMessages(conversationStore.activeConversation.id)
}

/** §25.1 打开 AI 区内部的 Conversation Drawer。 */
function openConversationDrawer() {
  conversationStore.drawerVisible = true
}

/** §25.1 打开 New Chat 对话框。 */
function openNewConversation() {
  dialogs.mode = 'create'
}

/** §25.1 切换 active Conversation(消息由 store 重新拉取,先清空再拉)。 */
async function handleConversationSelected(conversation) {
  const id = conversation?.id

  if (id === null || id === undefined) {
    return
  }

  await conversationStore.openConversation(id)
  conversationStore.closeConversationDrawer()
}

/**
 * §25.1 handleSend():
 * 没有 active Conversation 时先自动创建一个 cities=[] 的新会话再发送,
 * 用户不需要为了随口问一句先手动 New Chat。
 */
async function handleSend(content) {
  const text = String(content ?? '').trim()

  if (!text || chatStore.isSending) {
    return
  }

  let conversation = conversationStore.activeConversation

  if (!conversation) {
    conversation = await conversationStore.createNewConversation([])
  }

  if (!conversation) {
    return
  }

  chatStore.clearDraftPrompt()

  const result = await chatStore.sendUserMessage(conversation.id, text)

  if (!result) {
    // 失败:把用户输入放回输入框,失败气泡也保留,两种方式都能重试。
    chatStore.setDraftPrompt(text)
  }
}

/** §25.1 applyRecommendedPrompt():只填入,不自动发送(§39)。 */
function applyRecommendedPrompt(prompt) {
  chatStore.setDraftPrompt(prompt)
}

onMounted(initializeChat)

defineExpose({ applyRecommendedPrompt })
</script>

<style scoped>
.tm-chat-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  min-height: 0;
  padding: 16px;
  overflow: hidden;
  background: var(--tm-surface);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius-lg);
  box-shadow: var(--tm-shadow-sm);
}

.tm-chat-header {
  display: flex;
  flex: none;
  gap: 10px;
  align-items: flex-start;
}

.tm-drawer-toggle {
  flex: none;
  width: 32px;
  height: 32px;
  font: inherit;
  font-size: 15px;
  color: var(--tm-primary-dark);
  cursor: pointer;
  background: var(--tm-primary-soft);
  border: 1px solid var(--tm-border);
  border-radius: 9px;
}

.tm-drawer-toggle:hover {
  border-color: var(--tm-primary);
}

.tm-chat-header-main {
  flex: 1;
  min-width: 0;
}

.tm-chat-title {
  margin: 0 0 3px;
  font-size: 15px;
  font-weight: 600;
  color: var(--tm-ink);
}

.tm-chat-header-cities {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.tm-conversation-cities {
  padding: 0;
  font: inherit;
  font-size: 12.5px;
  color: var(--tm-primary-dark);
  text-align: left;
  cursor: pointer;
  background: none;
  border: 0;
  overflow-wrap: anywhere;
}

.tm-conversation-cities:hover:not(:disabled) {
  text-decoration: underline;
}

.tm-conversation-cities:disabled {
  color: var(--tm-muted);
  cursor: default;
}

.tm-edit-cities-btn {
  flex: none;
  padding: 1px 8px;
  font: inherit;
  font-size: 12px;
  color: var(--tm-primary-dark);
  cursor: pointer;
  background: var(--tm-page-bg);
  border: 1px solid var(--tm-border);
  border-radius: 999px;
}

.tm-edit-cities-btn:hover:not(:disabled) {
  border-color: var(--tm-primary);
}

.tm-edit-cities-btn:disabled {
  color: var(--tm-muted);
  cursor: default;
  opacity: 0.7;
}

.tm-new-chat-btn {
  flex: none;
}

.tm-chat-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.tm-chat-welcome {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  justify-content: center;
  min-height: 0;
  padding: 8px;
}

.tm-chat-welcome-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: var(--tm-primary-dark);
}

.tm-chat-welcome-text {
  max-width: 520px;
  margin: 0;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--tm-muted);
}

.tm-chat-welcome-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-left: 18px;
  margin: 0;
  font-size: 13px;
  color: var(--tm-muted);
}

.tm-chat-error {
  flex: none;
  margin: 0;
  font-size: 12.5px;
  color: #c45656;
}
</style>
