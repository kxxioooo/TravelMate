<template>
  <div class="tm-empty-state">
    <el-icon class="tm-empty-state-icon"><Compass /></el-icon>
    <p class="tm-empty-state-title">{{ titleText }}</p>
    <p v-if="description" class="tm-empty-state-desc">{{ description }}</p>
  </div>
</template>

<script setup>
import { Compass } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatLocalizedUnknown } from '../../utils/i18nDisplay'

/**
 * 通用空状态。
 *
 * 纯展示组件:景点无结果、餐厅无结果、API 返回空数组时复用。
 * 标题 / 描述由父组件传入(已经是当前语言的文案);
 * 万一传空,用当前语言的"暂无信息"兜底,不会渲染 undefined。
 */
const props = defineProps({
  title: { type: String, default: '' },
  description: { type: String, default: '' },
})

const { t } = useI18n()

const titleText = computed(() => formatLocalizedUnknown(props.title, t))
</script>

<style scoped>
.tm-empty-state {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  padding: 48px 16px;
  color: var(--tm-muted);
  text-align: center;
}

.tm-empty-state-icon {
  font-size: 34px;
  color: #b9d3cf;
}

.tm-empty-state-title {
  margin: 4px 0 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--tm-ink);
}

.tm-empty-state-desc {
  max-width: 420px;
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
}
</style>
