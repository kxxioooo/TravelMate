<template>
  <section class="tm-food-tab">
    <div class="tm-tab-toolbar">
      <el-input
        v-model="keyword"
        class="tm-food-search"
        :placeholder="t('food.search_placeholder')"
        clearable
        @keyup.enter="submitSearch"
        @clear="resetToFeatured"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-button class="tm-food-search-btn" type="primary" @click="submitSearch">
        {{ t('food.search_button') }}
      </el-button>
      <el-button v-if="isSearchMode" text @click="resetToFeatured">
        {{ t('food.back_to_featured') }}
      </el-button>
    </div>

    <div v-loading="foodStore.isLoading" class="tm-food-list">
      <template v-if="isSearchMode">
        <p class="tm-food-mode-hint">
          {{
            t('food.search_hint', {
              keyword: displayOrUnknown(foodStore.keyword),
              count: foodStore.restaurantResults.length,
            })
          }}
        </p>

        <div v-if="foodStore.restaurantResults.length" class="tm-restaurant-result-list">
          <RestaurantSearchResultCard
            v-for="item in foodStore.restaurantResults"
            :key="item.poi_id"
            :restaurant="item"
            @open-detail="openRestaurant"
          />
        </div>

        <EmptyState
          v-else-if="!foodStore.isLoading"
          :title="t('food.empty_search_title')"
          :description="searchEmptyDescription"
        />
      </template>

      <template v-else>
        <div v-if="foodStore.featuredFoods.length" class="tm-card-grid tm-food-grid">
          <FoodCard
            v-for="food in foodStore.featuredFoods"
            :key="food.name"
            :food="food"
            @open-restaurant="openRestaurant"
          />
        </div>

        <EmptyState
          v-else-if="!foodStore.isLoading"
          :title="t('food.empty_default_title')"
          :description="featuredEmptyDescription"
        />
      </template>
    </div>

    <LoadMoreButton
      v-if="isSearchMode && foodStore.hasMore"
      :loading="foodStore.isLoading"
      @load-more="loadMore"
    />
  </section>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFoodStore } from '../../stores/food'
import { displayOrUnknown } from '../../utils/display'
import { formatLocalizedError } from '../../utils/i18nDisplay'
import EmptyState from '../common/EmptyState.vue'
import LoadMoreButton from '../common/LoadMoreButton.vue'
import FoodCard from './FoodCard.vue'
import RestaurantSearchResultCard from './RestaurantSearchResultCard.vue'

/**
 * 美食 Tab,两种模式:
 *   featured —— 10 种代表性美食 × 每种 2 家代表餐厅(第一次切到本 Tab 才加载);
 *   search   —— 关键词命中的餐厅结果列表,支持 Load More。
 *
 * 英文关键词(`hot pot`)由后端转成经验证的中文关键词查高德;
 * 输入框始终保留用户原文,不做改写。
 */
const props = defineProps({
  city: { type: Object, default: null },
  active: { type: Boolean, default: false },
})

const emit = defineEmits(['search'])

const { t } = useI18n()

const foodStore = useFoodStore()

const keyword = ref('')
/** 本城市是否已经请求过十大美食,避免重复请求。 */
const requested = ref(false)

const isSearchMode = computed(() => foodStore.mode === 'search')

/** 餐厅搜索空态描述:有错误就显示本地化错误,否则显示引导文案。 */
const searchEmptyDescription = computed(() =>
  foodStore.error
    ? formatLocalizedError(foodStore.error, { t, fallbackKey: 'food.empty_search_desc' })
    : t('food.empty_search_desc'),
)

/** 十大美食空态描述。 */
const featuredEmptyDescription = computed(() =>
  foodStore.error
    ? formatLocalizedError(foodStore.error, { t, fallbackKey: 'food.empty_default_desc' })
    : t('food.empty_default_desc'),
)

/** 第一次真正进入美食 Tab 时再加载十大美食。 */
function ensureFeaturedLoaded() {
  if (requested.value) {
    return
  }
  // 用户正在看餐厅搜索结果时,不要用十大美食把结果覆盖掉。
  if (foodStore.mode === 'search') {
    return
  }
  if (foodStore.featuredFoods.length > 0 || foodStore.isLoading) {
    return
  }

  requested.value = true
  foodStore.loadFeaturedFoods(props.city)
}

/** 提交搜索:空关键词回默认,非空切到餐厅结果模式。 */
function submitSearch() {
  const value = keyword.value.trim()
  if (!value) {
    resetToFeatured()
    return
  }

  emit('search', value)
}

/** 只在 search 模式 + hasMore 时翻页。 */
function loadMore() {
  if (!isSearchMode.value || !foodStore.hasMore || foodStore.isLoading) {
    return
  }

  foodStore.loadMoreRestaurants(props.city)
}

/** 恢复到 10 种美食 × 2 家代表餐厅。 */
function resetToFeatured() {
  keyword.value = ''
  requested.value = true
  foodStore.loadFeaturedFoods(props.city)
}

/** 打开餐厅详情:交给 store,弹窗由 CityWorkspace 承载。 */
function openRestaurant(poiId) {
  foodStore.openRestaurantDetail(poiId)
}

watch(
  () => props.active,
  (isActive) => {
    if (isActive) {
      ensureFeaturedLoaded()
    }
  },
  { immediate: true },
)

watch(
  () => props.city?.adcode,
  () => {
    keyword.value = ''
    requested.value = false
  },
)
</script>

<style scoped>
.tm-food-tab {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tm-tab-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.tm-food-search {
  width: 320px;
  max-width: 100%;
}

.tm-food-mode-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--tm-muted);
}

.tm-food-list {
  min-height: 160px;
}

.tm-restaurant-result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 900px) {
  .tm-food-search {
    width: 100%;
  }
}
</style>
