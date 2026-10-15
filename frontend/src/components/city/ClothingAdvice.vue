<template>
  <p class="tm-clothing-advice">
    <el-icon class="tm-clothing-advice-icon"><Sunny /></el-icon>
    <span class="tm-clothing-advice-label">穿衣建议:</span>
    <span class="tm-clothing-advice-text">{{ displayOrUnknown(text) }}</span>
  </p>
</template>

<script setup>
import { Sunny } from '@element-plus/icons-vue'

import { displayOrUnknown } from '../../utils/display'

/**
 * 穿衣建议,纯展示。
 *
 * 只接收后端归一化后的建议文本;天气接口不可用时后端会给空值,
 * 这里统一显示"暂无信息"。
 */
defineProps({
  text: { type: String, default: '' },
})
</script>

<style scoped>
.tm-clothing-advice {
  display: flex;
  gap: 6px;
  align-items: center;
  margin: 0;
  font-size: 13px;
  color: var(--tm-ink);
}

.tm-clothing-advice-icon {
  color: var(--tm-accent);
}

.tm-clothing-advice-label {
  color: var(--tm-muted);
}

.tm-clothing-advice-text {
  font-weight: 500;
}
</style>
