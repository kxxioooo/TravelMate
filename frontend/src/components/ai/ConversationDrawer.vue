<template>
  <!--
    §19 Conversation Drawer:只存在于 AI 区内部,默认隐藏。
    网站 Sidebar 里永远不出现任何对话历史。
  -->
  <aside
    v-show="conversationStore.drawerVisible"
    class="tm-conversation-drawer"
    role="dialog"
    aria-label="Conversations"
  >
    <header class="tm-drawer-header">
      <h3 class="tm-drawer-title">Conversations</h3>
      <button type="button" class="tm-drawer-close" aria-label="关闭会话列表" @click="handleClose">
        ✕
      </button>
    </header>

    <button type="button" class="tm-drawer-new-chat" @click="openNewChat">+ New Chat</button>

    <p v-if="conversationStore.isLoading && !conversationStore.items.length" class="tm-drawer-hint">
      正在加载会话…
    </p>
    <p v-else-if="!conversationStore.items.length" class="tm-drawer-hint">
      还没有会话,点上面的 + New Chat 开始。
    </p>

    <ul v-else class="tm-drawer-list">
      <li v-for="item in conversationStore.items" :key="item.id">
        <button
          type="button"
          class="tm-conversation-item"
          :class="{ 'is-active': item.id === conversationStore.activeConversation?.id }"
          @click="selectConversation(item)"
        >
          <span class="tm-conversation-item-title">{{ fallbackConversationTitle(item.title) }}</span>
          <span class="tm-conversation-item-cities">
            {{ (item.cities ?? []).map((city) => city.city_name).join(' · ') || '未选择城市' }}
          </span>
        </button>
      </li>
    </ul>
  </aside>
</template>

<script setup>
import { watch } from 'vue'

import { useConversationStore } from '../../stores/conversations'
import { fallbackConversationTitle } from '../../utils/chat'

const emit = defineEmits(['new-chat'])

const conversationStore = useConversationStore()

/** §19 loadHistory():打开 Drawer 时刷新会话列表。 */
async function loadHistory() {
  await conversationStore.loadConversations()
}

/** §19 selectConversation():切换 active(消息由 chat store 重新拉取)并关闭 Drawer。 */
async function selectConversation(item) {
  if (!item || item.id === null || item.id === undefined) {
    return
  }

  await conversationStore.openConversation(item.id)
  handleClose()
}

/** §19 openNewChat():打开 NewConversationDialog,由 ChatPanel 负责弹窗。 */
function openNewChat() {
  handleClose()
  emit('new-chat')
}

/** §19 handleClose():关闭 Drawer。 */
function handleClose() {
  conversationStore.closeConversationDrawer()
}

/** Drawer 每次被打开时都刷新一次列表(新建会话后标题 / 顺序会变)。 */
watch(
  () => conversationStore.drawerVisible,
  (visible) => {
    if (visible) {
      loadHistory()
    }
  },
)
</script>

<style scoped>
.tm-conversation-drawer {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 6;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(280px, 100%);
  padding: 14px;
  overflow-y: auto;
  background: var(--tm-surface);
  border-right: 1px solid var(--tm-border);
  box-shadow: var(--tm-shadow-md);
}

.tm-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tm-drawer-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--tm-ink);
}

.tm-drawer-close {
  padding: 0 4px;
  font: inherit;
  font-size: 13px;
  color: var(--tm-muted);
  cursor: pointer;
  background: none;
  border: 0;
}

.tm-drawer-close:hover {
  color: var(--tm-ink);
}

.tm-drawer-new-chat {
  width: 100%;
  padding: 9px 12px;
  font: inherit;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--tm-primary-dark);
  cursor: pointer;
  background: var(--tm-primary-soft);
  border: 1px solid var(--tm-border);
  border-radius: 10px;
}

.tm-drawer-new-chat:hover {
  border-color: var(--tm-primary);
}

.tm-drawer-hint {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--tm-muted);
}

.tm-drawer-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.tm-conversation-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 9px 10px;
  font: inherit;
  text-align: left;
  cursor: pointer;
  background: var(--tm-page-bg);
  border: 1px solid transparent;
  border-radius: 10px;
}

.tm-conversation-item:hover {
  border-color: var(--tm-primary);
}

.tm-conversation-item.is-active {
  background: var(--tm-primary-soft);
  border-color: var(--tm-primary);
}

.tm-conversation-item-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--tm-ink);
  overflow-wrap: anywhere;
}

.tm-conversation-item-cities {
  font-size: 12px;
  color: var(--tm-muted);
  overflow-wrap: anywhere;
}
</style>
