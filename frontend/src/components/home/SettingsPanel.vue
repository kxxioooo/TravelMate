<template>
  <div class="tm-settings">
    <el-descriptions :column="1" border>
      <el-descriptions-item :label="t('app.settings_username')">
        {{ authStore.user?.username ?? '-' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('app.settings_email')">
        {{ authStore.user?.email ?? '-' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('app.settings_version')">v0.3.1</el-descriptions-item>
    </el-descriptions>

    <p class="tm-settings-hint">{{ t('app.settings_hint') }}</p>

    <footer class="tm-settings-footer">
      <el-button text @click="closePanel">{{ t('common.close') }}</el-button>
    </footer>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '../../stores/auth'

const { t } = useI18n()

const authStore = useAuthStore()

const emit = defineEmits(['close'])

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

.tm-settings-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
