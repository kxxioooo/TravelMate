<template>
  <!--
    §25.3 纯展示:0 个业务函数,只有 user / assistant 两种气泡。
    安全文本渲染(不使用 v-html),前端不展示任何内部 payload / 思维链(§43)。
  -->
  <article
    class="tm-chat-message"
    :class="message.role === 'user' ? 'tm-chat-message--user' : 'tm-chat-message--assistant'"
  >
    <p class="tm-chat-message-bubble">{{ message.content }}</p>

    <p v-if="message.pending" class="tm-chat-message-state">发送中…</p>
    <button
      v-else-if="message.failed"
      type="button"
      class="tm-chat-message-retry"
      @click="$emit('retry', message)"
    >
      发送失败,点击重试
    </button>
  </article>
</template>

<script setup>
defineProps({
  message: { type: Object, required: true },
})

defineEmits(['retry'])
</script>

<style scoped>
.tm-chat-message {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 92%;
}

.tm-chat-message--user {
  align-self: flex-end;
  align-items: flex-end;
}

.tm-chat-message--assistant {
  align-self: flex-start;
  align-items: flex-start;
}

.tm-chat-message-bubble {
  padding: 10px 13px;
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  border-radius: var(--tm-radius);
}

.tm-chat-message--user .tm-chat-message-bubble {
  color: #fff;
  background: var(--tm-primary);
  border-bottom-right-radius: 4px;
}

.tm-chat-message--assistant .tm-chat-message-bubble {
  color: var(--tm-ink);
  background: var(--tm-surface);
  border: 1px solid var(--tm-border);
  border-bottom-left-radius: 4px;
}

.tm-chat-message-state {
  margin: 0;
  font-size: 12px;
  color: var(--tm-muted);
}

.tm-chat-message-retry {
  padding: 0;
  font: inherit;
  font-size: 12px;
  color: #c45656;
  cursor: pointer;
  background: none;
  border: 0;
}

.tm-chat-message-retry:hover {
  text-decoration: underline;
}
</style>
