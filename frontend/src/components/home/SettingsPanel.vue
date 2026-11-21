<template>
  <div class="tm-settings">
    <el-descriptions :column="1" border>
      <el-descriptions-item :label="t('app.settings_username')">
        {{ authStore.user?.username ?? '-' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('app.settings_email')">
        {{ authStore.user?.email ?? '-' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('app.settings_version')">v0.3.2</el-descriptions-item>
    </el-descriptions>

    <p class="tm-settings-hint">{{ t('app.settings_hint') }}</p>

    <!-- 任务书 §5.4:记忆与隐私入口(两个授权开关 + 画像 + 来源管理) -->
    <section class="tm-settings-memory">
      <div class="tm-settings-memory-text">
        <strong>{{ t('memory.entry_title') }}</strong>
        <small>{{ t('memory.entry_hint') }}</small>
      </div>
      <el-button class="tm-memory-open" @click="memoryVisible = true">
        {{ t('memory.entry_action') }}
      </el-button>
    </section>

    <footer class="tm-settings-footer">
      <el-button text @click="closePanel">{{ t('common.close') }}</el-button>
    </footer>

    <el-dialog
      v-model="memoryVisible"
      :title="t('memory.entry_title')"
      width="640px"
      class="tm-memory-dialog"
      @open="onMemoryOpen"
    >
      <MemorySettingsPanel />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '../../stores/auth'
import MemorySettingsPanel from '../memory/MemorySettingsPanel.vue'

const { t } = useI18n()

const authStore = useAuthStore()

const emit = defineEmits(['close'])

const memoryVisible = ref(false)

/** 每次打开都拉一次最新状态(授权可能在别的标签页改过)。 */
function onMemoryOpen() {
  memoryVisible.value = true
}

/** 关闭面板。 */
function closePanel() {
  emit('close')
}
</script>

<style scoped>
.tm-settings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tm-settings-hint {
  margin: 0;
  font-size: 13px;
  color: var(--tm-muted);
}

.tm-settings-memory {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--tm-page-bg);
  border: 1px solid var(--tm-border);
  border-radius: 10px;
}

.tm-settings-memory-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
  color: var(--tm-ink);
}

.tm-settings-memory-text small {
  font-size: 12px;
  line-height: 1.5;
  color: var(--tm-muted);
}

.tm-settings-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
