<template>
  <div class="tm-prompts">
    <p class="tm-prompts-hint">{{ t('chat.prompts_hint') }}</p>

    <ul class="tm-prompts-list">
      <li v-for="key in PROMPT_KEYS" :key="key">
        <button type="button" class="tm-prompt-item" @click="handlePromptClick(t(key))">
          <el-icon class="tm-prompt-icon"><MagicStick /></el-icon>
          <span>{{ t(key) }}</span>
        </button>
      </li>
    </ul>

    <footer class="tm-prompts-footer">
      <el-button text @click="closePanel">{{ t('common.close') }}</el-button>
    </footer>
  </div>
</template>

<script setup>
import { MagicStick } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

/**
 * 推荐问题面板。
 *
 * 只保存 i18n key:推荐问题属于应用控制的文案,必须随语言即时切换;
 * 点击后把**当前语言**的问句抛给父组件(HomeView → ChatPanel),
 * 只填入输入框、不自动发送。
 */
const PROMPT_KEYS = ['chat.prompt_1', 'chat.prompt_2', 'chat.prompt_3', 'chat.prompt_4']

const { t } = useI18n()

const emit = defineEmits(['prompt-selected', 'close'])

/** 点击推荐问题,把当前语言的文本抛给父组件。 */
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
