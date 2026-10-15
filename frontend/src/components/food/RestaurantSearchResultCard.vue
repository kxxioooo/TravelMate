<template>
  <article class="tm-restaurant-result-card">
    <span class="tm-restaurant-result-name">{{ displayOrUnknown(restaurant?.name) }}</span>
    <el-button class="tm-restaurant-detail-btn" type="primary" plain @click="openDetail">
      详情
    </el-button>
  </article>
</template>

<script setup>
import { displayOrUnknown } from '../../utils/display'

/**
 * 搜索某种美食后的餐厅结果卡片。
 *
 * 同样只显示餐厅名称 + 详情按钮,不在列表页堆地址 / 电话。
 */
const props = defineProps({
  restaurant: { type: Object, required: true },
})

const emit = defineEmits(['open-detail'])

/** 抛给父级,由 store 统一请求详情。 */
function openDetail() {
  if (!props.restaurant?.poi_id) {
    return
  }

  emit('open-detail', props.restaurant.poi_id)
}
</script>

<style scoped>
.tm-restaurant-result-card {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--tm-surface);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius);
  box-shadow: var(--tm-shadow-sm);
}

.tm-restaurant-result-name {
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  color: var(--tm-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
