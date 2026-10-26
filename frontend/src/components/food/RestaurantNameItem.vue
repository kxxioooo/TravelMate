<template>
  <div class="tm-restaurant-name-item">
    <span class="tm-restaurant-name">{{ restaurantName }}</span>
    <el-button class="tm-restaurant-detail-btn" type="primary" link @click="openDetail">
      {{ t('restaurant.detail_button') }}
    </el-button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { displayOrUnknown } from '../../utils/display'
import { displayBilingualName } from '../../utils/i18nDisplay'

/**
 * 默认美食页里最简的代表餐厅元素:只显示餐厅名称 + 详情按钮。
 *
 * 英文模式名称是 `Verified English Name (高德中文原名)`;
 * 列表页刻意不塞地址 / 电话,一切细节留给详情弹窗。
 */
const props = defineProps({
  restaurant: { type: Object, required: true },
})

const emit = defineEmits(['open-detail'])

const { t, locale } = useI18n()

const restaurantName = computed(
  () =>
    displayBilingualName(
      props.restaurant?.name,
      props.restaurant?.name_en,
      locale.value,
    ) || displayOrUnknown(null),
)

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
