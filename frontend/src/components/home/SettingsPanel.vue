<template>
  <div class="tm-settings">
    <el-descriptions :column="1" border>
      <el-descriptions-item label="Username">
        {{ authStore.user?.username ?? '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="Email">
        {{ authStore.user?.email ?? '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="Version">v0.1</el-descriptions-item>
    </el-descriptions>

    <p class="tm-settings-hint">v0.1 只展示基础信息,复杂账户设置留待后续版本。</p>

    <footer class="tm-settings-footer">
      <el-button text @click="closePanel">关闭</el-button>
    </footer>
  </div>
</template>

<script setup>
import { useAuthStore } from '../../stores/auth'

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
