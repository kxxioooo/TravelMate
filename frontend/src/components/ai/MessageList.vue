<template>
  <div ref="listRef" class="tm-message-list">
    <p v-if="!messages.length" class="tm-message-list-empty">
      {{ t('chat.no_messages') }}
    </p>

    <!-- 历史消息的 content 原样渲染:切换语言不翻译、不覆盖(规格 §8.2) -->
    <ChatMessage
      v-for="message in messages"
      :key="message.id"
      :message="message"
      @retry="$emit('retry', $event.content)"
    />
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import ChatMessage from './ChatMessage.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
})

defineEmits(['retry'])

const { t } = useI18n()

const listRef = ref(null)

/** §25.2 消息数量变化后,等 DOM 更新完再滚到底部。 */
function scrollToBottom() {
  nextTick(() => {
    const container = listRef.value
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

watch(() => props.messages.length, scrollToBottom)
</script>

<style scoped>
.tm-message-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding: 4px 2px 8px;
  overflow-y: auto;
}

.tm-message-list-empty {
  margin: auto 0;
  font-size: 13px;
  color: var(--tm-muted);
  text-align: center;
}
</style>
