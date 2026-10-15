<template>
  <div class="tm-prompts">
    <p class="tm-prompts-hint">
      点击后会把问题填入 AI 区输入框(不会自动发送),你可以改完再发。
    </p>

    <ul class="tm-prompts-list">
      <li v-for="prompt in PROMPTS" :key="prompt">
        <button type="button" class="tm-prompt-item" @click="handlePromptClick(prompt)">
          <el-icon class="tm-prompt-icon"><MagicStick /></el-icon>
          <span>{{ prompt }}</span>
        </button>
      </li>
    </ul>

    <footer class="tm-prompts-footer">
      <el-button text @click="closePanel">关闭</el-button>
    </footer>
  </div>
</template>

<script setup>
import { MagicStick } from '@element-plus/icons-vue'

/** v0.1 静态示例;v0.3 保留此组件(函数仍为 2 个),点击后进入真实 Chat 输入。 */
const PROMPTS = [
  '帮我规划成都三日游',
  '推荐适合自然风景爱好者的城市',
  '杭州和苏州应该怎么选择?',
  '预算 3000 元去哪里玩?',
]

const emit = defineEmits(['prompt-selected', 'close'])

/** 点击推荐问题,把文本抛给父组件(HomeView → ChatPanel.applyRecommendedPrompt)。 */
function handlePromptClick(prompt) {
  emit('prompt-selected', prompt)
}

/** 关闭面板。 */
function closePanel() {
  emit('close')
}
</script>

<style scoped>
.tm-prompts {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tm-prompts-hint {
  margin: 0;
  font-size: 13px;
  color: var(--tm-muted);
}

.tm-prompts-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.tm-prompt-item {
  display: flex;
  gap: 10px;
  align-items: center;
  width: 100%;
  padding: 12px 14px;
  font: inherit;
  color: var(--tm-ink);
  text-align: left;
  cursor: pointer;
  background: var(--tm-page-bg);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius);
  transition: border-color 0.15s ease, background 0.15s ease;
}

.tm-prompt-item:hover {
  background: var(--tm-primary-soft);
  border-color: var(--tm-primary);
}

.tm-prompt-icon {
  color: var(--tm-primary);
}

.tm-prompts-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
