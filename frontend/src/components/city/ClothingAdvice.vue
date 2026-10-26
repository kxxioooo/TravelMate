<template>
  <p class="tm-clothing-advice">
    <el-icon class="tm-clothing-advice-icon"><Sunny /></el-icon>
    <span class="tm-clothing-advice-label">{{ t('city.clothing_advice') }}</span>
    <span class="tm-clothing-advice-text">{{ adviceText }}</span>
  </p>
</template>

<script setup>
import { Sunny } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { resolveClothingLabels } from '../../constants/localizedTerms'
import { displayOrUnknown } from '../../utils/display'

/**
 * 穿衣建议,纯展示。
 *
 * v0.3.1:优先用后端的 `clothing_advice_codes` 走 `t('clothing.' + code)`,
 * 保证英文模式不残留中文;后端还没返回 codes 时退回原始建议文本
 * (向后兼容降级 —— 宁可显示原文,也不猜建议内容)。
 */
const props = defineProps({
  /** 后端原始建议文本(兼容 v0.3)。 */
  text: { type: String, default: '' },
  /** 语言无关的建议枚举(跨端契约 §3)。 */
  codes: { type: Array, default: () => [] },
})

const { t } = useI18n()

const adviceText = computed(() => {
  const labels = resolveClothingLabels(props.codes, t)

  if (labels.length) {
    return labels.join(' / ')
  }

  return displayOrUnknown(props.text)
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
