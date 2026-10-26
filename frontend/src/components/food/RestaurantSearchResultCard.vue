<template>
  <article class="tm-restaurant-result-card">
    <span class="tm-restaurant-result-name">{{ restaurantName }}</span>
    <el-button class="tm-restaurant-detail-btn" type="primary" plain @click="openDetail">
      {{ t('restaurant.detail_button') }}
    </el-button>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { displayOrUnknown } from '../../utils/display'
import { displayBilingualName } from '../../utils/i18nDisplay'

/**
 * 搜索某种美食后的餐厅结果卡片。
 *
 * 同样只显示餐厅名称 + 详情按钮;英文模式名称是
 * `English Name (高德中文原名)`,poi_id 不变。
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
