<template>
  <div class="tm-restaurant-name-item">
    <span class="tm-restaurant-name">{{ displayOrUnknown(restaurant?.name) }}</span>
    <el-button class="tm-restaurant-detail-btn" type="primary" link @click="openDetail">
      详情
    </el-button>
  </div>
</template>

<script setup>
import { displayOrUnknown } from '../../utils/display'

/**
 * 默认美食页里最简的代表餐厅元素:只显示餐厅名称 + 详情按钮。
 *
 * 列表页刻意不塞地址 / 电话,一切细节留给详情弹窗。
 */
const props = defineProps({
  restaurant: { type: Object, required: true },
})

const emit = defineEmits(['open-detail'])

/** 把 poi_id 抛给父级,由 store 统一请求详情。 */
function openDetail() {
  if (!props.restaurant?.poi_id) {
    return
  }

  emit('open-detail', props.restaurant.poi_id)
}
</script>

<style scoped>
.tm-restaurant-name-item {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  padding: 2px 0;
}

.tm-restaurant-name {
  overflow: hidden;
  font-size: 13px;
  color: var(--tm-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
