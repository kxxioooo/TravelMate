<template>
  <section class="tm-ai">
    <header class="tm-ai-header">
      <div>
        <h2 class="tm-ai-title">AI Travel Agent</h2>
        <p class="tm-ai-desc">
          v0.1 这里只是占位。接入 DeepSeek 后会结合你的偏好和所选城市直接生成行程。
        </p>
      </div>
      <el-tag type="warning" effect="light" round>Coming Soon</el-tag>
    </header>

    <el-input
      v-model="draftPrompt"
      type="textarea"
      :rows="4"
      resize="none"
      placeholder="例如:帮我规划成都三日游"
    />

    <div class="tm-ai-actions">
      <span class="tm-muted">v0.3 启用真实对话</span>
      <el-button type="primary" @click="handleFakeSubmit">发送</el-button>
    </div>
  </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { ref } from 'vue'

/** 待发送的草稿;v0.3 会被真正的 ChatPanel 取代。 */
const draftPrompt = ref('')

/** 接收 Recommended Prompt:只填入,不发送。 */
function setDraftPrompt(prompt) {
  draftPrompt.value = String(prompt ?? '')
  ElMessage.info('已填入推荐问题,v0.1 暂不发送')
}

/** v0.1 不调用任何 AI 接口。 */
function handleFakeSubmit() {
  ElMessage.info('AI Travel Agent 将在 v0.3 启用')
}

defineExpose({ setDraftPrompt })
</script>

<style scoped>
.tm-ai {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px;
  background: var(--tm-surface);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius-lg);
  box-shadow: var(--tm-shadow-sm);
}

.tm-ai-header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
}

.tm-ai-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
  color: var(--tm-ink);
}

.tm-ai-desc {
  max-width: 560px;
  margin: 0;
  font-size: 13px;
  color: var(--tm-muted);
}

.tm-ai-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}
</style>
