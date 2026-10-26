<template>
  <article class="tm-food-card">
    <div class="tm-food-card-cover">
      <el-image
        v-if="coverUrl"
        class="tm-food-card-image"
        :src="coverUrl"
        fit="cover"
        :alt="foodName"
      >
        <template #error>
          <div class="tm-food-card-placeholder">
            <el-icon><Food /></el-icon>
          </div>
        </template>
        <template #placeholder>
          <div class="tm-food-card-placeholder">
            <el-icon><Food /></el-icon>
          </div>
        </template>
      </el-image>
      <div v-else class="tm-food-card-placeholder">
        <el-icon><Food /></el-icon>
        <span>{{ t('common.no_image') }}</span>
      </div>
    </div>

    <div class="tm-food-card-body">
      <h3 class="tm-food-card-name">{{ foodName }}</h3>
      <p class="tm-food-card-desc">{{ foodDescription }}</p>

      <div class="tm-food-card-restaurants">
        <p class="tm-food-card-restaurants-title">{{ t('food.representative_restaurants') }}</p>
        <template v-if="restaurants.length">
          <RestaurantNameItem
            v-for="restaurant in restaurants"
            :key="restaurant.poi_id"
            :restaurant="restaurant"
            @open-detail="openRestaurant"
          />
        </template>
        <p v-else class="tm-food-card-no-restaurant">{{ t('food.no_restaurant') }}</p>
      </div>
    </div>
  </article>
</template>

<script setup>
import { Food } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { displayOrUnknown, safePhotoUrls } from '../../utils/display'
import { displayBilingualName, formatLocalizedEntity } from '../../utils/i18nDisplay'
import RestaurantNameItem from './RestaurantNameItem.vue'

/** 每种美食最多 2 家代表餐厅(§1 第 16 条)。 */
const MAX_RESTAURANTS = 2

/**
 * 美食卡片:美食图片 + 名称 + 简短介绍 + 2 家代表餐厅(名称 + 详情)。
 *
 * 英文模式名称是 `Mapo Tofu (麻婆豆腐)`;介绍优先用后端 `description_en`,
 * 没有英文介绍时退回原文(降级,不伪造),poi_id / 图片等事实字段不变。
 */
const props = defineProps({
  food: { type: Object, required: true },
})

const emit = defineEmits(['open-restaurant'])

const { t, locale } = useI18n()

const coverUrl = computed(() => safePhotoUrls(props.food?.cover_photo)[0] ?? '')

const foodName = computed(
  () =>
    displayBilingualName(props.food?.name, props.food?.name_en, locale.value) ||
    displayOrUnknown(null),
)

/** 名称 + 介绍的本地化(介绍按当前语言选取,不翻译)。 */
const localizedFood = computed(() => formatLocalizedEntity(props.food, locale.value))

const foodDescription = computed(
  () => localizedFood.value.description || displayOrUnknown(null),
)

const restaurants = computed(() =>
  (Array.isArray(props.food?.representative_restaurants) ? props.food.representative_restaurants : [])
    .filter((item) => item && item.poi_id)
    .slice(0, MAX_RESTAURANTS),
)

/** 把餐厅详情意图抛给父级 → store。 */
function openRestaurant(poiId) {
  emit('open-restaurant', poiId)
}
</script>

<style scoped>
.tm-food-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--tm-surface);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius);
  box-shadow: var(--tm-shadow-sm);
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}

.tm-food-card:hover {
  box-shadow: var(--tm-shadow-md);
  transform: translateY(-2px);
}

.tm-food-card-cover {
  height: 132px;
  background: var(--tm-page-bg);
}

.tm-food-card-image {
  width: 100%;
  height: 100%;
}

.tm-food-card-placeholder {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: var(--tm-muted);
  background: repeating-linear-gradient(45deg, #f7f3ea, #f7f3ea 10px, #f2ece0 10px, #f2ece0 20px);
}

.tm-food-card-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px 14px;
}

.tm-food-card-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--tm-primary-dark);
}

.tm-food-card-desc {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.6;
  color: var(--tm-muted);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.tm-food-card-restaurants {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 8px;
  margin-top: auto;
  border-top: 1px dashed var(--tm-border);
}

.tm-food-card-restaurants-title {
  margin: 0 0 2px;
  font-size: 12px;
  color: var(--tm-muted);
}

.tm-food-card-no-restaurant {
  margin: 0;
  font-size: 13px;
  color: var(--tm-muted);
}
</style>
