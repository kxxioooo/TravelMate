<template>
  <div class="tm-chat-input">
    <textarea
      v-model="text"
      class="tm-chat-input-field"
      rows="2"
      placeholder="问点什么,例如:帮我规划成都三日游"
      @keydown="handleKeydown"
    />

    <div class="tm-chat-input-actions">
      <span class="tm-chat-input-hint">Enter 发送,Shift + Enter 换行</span>
      <el-button type="primary" class="tm-chat-send-btn" @click="submitMessage">发送</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  /** 外部草稿(Recommended Prompt 或失败后回填的输入)。 */
  draft: { type: String, default: '' },
  sending: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])

const text = ref('')

/**
 * §25.4 applyDraft():外部 draft 改变时同步输入框。
 *
 * ChatPanel 重新挂载(主页布局切换)时,这里也会用 store 里的 draftPrompt
 * 重新填一次,所以推荐问题不会因为组件重挂而丢掉。
 */
function applyDraft(prompt) {
  text.value = String(prompt ?? '')
}

/** §25.4 handleKeydown():Enter 发送,Shift + Enter 换行。 */
function handleKeydown(event) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) {
    return
  }

  event.preventDefault()
  submitMessage()
}

/** §25.4 submitMessage():空文本不发送,发送时 emit 给 ChatPanel。 */
function submitMessage() {
  const content = String(text.value ?? '').trim()

  if (!content || props.sending) {
    return
  }

  emit('send', content)
  text.value = ''
}

// immediate:挂载时立刻读一次外部 draft(§25.1 要求 ChatPanel 挂载时读 store)。
watch(() => props.draft, applyDraft, { immediate: true })
</script>

<style scoped>
.tm-chat-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--tm-border);
}

.tm-chat-input-field {
  width: 100%;
  padding: 10px 12px;
  font: inherit;
  font-size: 14px;
  line-height: 1.6;
  color: var(--tm-ink);
  resize: vertical;
  background: var(--tm-page-bg);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius);
}

.tm-chat-input-field:focus {
  border-color: var(--tm-primary);
  outline: none;
}

.tm-chat-input-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.tm-chat-input-hint {
  font-size: 12px;
  color: var(--tm-muted);
}
</style>
