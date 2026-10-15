<template>
  <div class="tm-city-workspace">
    <!-- 默认 ≈80% 城市信息区 + ≈20% AI 区;城市区 min 520px,AI 区 min 320px -->
    <el-splitter class="tm-splitter">
      <el-splitter-panel class="tm-splitter-city" :min="520">
        <div class="tm-city-column">
          <template v-if="city">
            <CityHeader
              :city="city"
              :weather="weather"
              :clothing-advice="clothingAdvice"
              :loading="weatherLoading"
            />

            <el-tabs v-model="activeTab" class="tm-city-tabs" @tab-change="switchTab">
              <el-tab-pane name="attractions" lazy>
                <template #label>
                  <span class="tm-tab-attractions">景点</span>
                </template>
                <AttractionTab
                  :city="city"
                  :active="activeTab === 'attractions'"
                  @search="handleAttractionSearch"
                />
              </el-tab-pane>

              <el-tab-pane name="food" lazy>
                <template #label>
                  <span class="tm-tab-food">美食</span>
                </template>
                <FoodTab :city="city" :active="activeTab === 'food'" @search="handleFoodSearch" />
              </el-tab-pane>
            </el-tabs>
          </template>

          <section v-else class="tm-city-welcome">
            <h1 class="tm-hero-title">你好,{{ username || '旅行者' }}</h1>
            <p class="tm-city-welcome-hint">
              在顶部搜索并选择一个城市,开始规划你的旅程。
            </p>
          </section>
        </div>
      </el-splitter-panel>

      <el-splitter-panel class="tm-splitter-ai" :min="320" size="20%">
        <div class="tm-ai-column">
          <slot name="ai" />
        </div>
      </el-splitter-panel>
    </el-splitter>

    <AttractionDetailDialog
      :detail="attractionStore.selectedDetail"
      :loading="attractionStore.isDetailLoading"
      @close="attractionStore.closeDetail()"
    />

    <RestaurantDetailDialog
      :detail="foodStore.selectedRestaurant"
      :loading="foodStore.isDetailLoading"
      @close="foodStore.closeRestaurantDetail()"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

import { useAttractionStore } from '../../stores/attractions'
import { useFoodStore } from '../../stores/food'
import AttractionDetailDialog from '../attractions/AttractionDetailDialog.vue'
import AttractionTab from '../attractions/AttractionTab.vue'
import RestaurantDetailDialog from '../food/RestaurantDetailDialog.vue'
import FoodTab from '../food/FoodTab.vue'
import CityHeader from './CityHeader.vue'

/** Tab 名称常量,避免魔法字符串散落。 */
const ATTRACTIONS_TAB = 'attractions'
const FOOD_TAB = 'food'

const props = defineProps({
  city: { type: Object, default: null },
  weather: { type: Object, default: null },
  clothingAdvice: { type: String, default: '' },
  weatherLoading: { type: Boolean, default: false },
  username: { type: String, default: '' },
})

const attractionStore = useAttractionStore()
const foodStore = useFoodStore()

/** 城市内容区当前 Tab,默认景点(§1 第 9 条)。 */
const activeTab = ref(ATTRACTIONS_TAB)

/**
 * 切换 Tab。
 *
 * 切到美食时,如果十大美食尚未加载,才第一次发起请求 —— 选城市时
 * 绝不预加载美食,降低首屏成本。
 */
function switchTab(tab) {
  activeTab.value = tab === FOOD_TAB ? FOOD_TAB : ATTRACTIONS_TAB

  if (activeTab.value === FOOD_TAB && !foodStore.featuredFoods.length && !foodStore.isLoading) {
    foodStore.loadFeaturedFoods(props.city)
  }
}

/** 景点搜索:交给景点 store(关键词非空才会走到这里)。 */
function handleAttractionSearch(keyword) {
  attractionStore.searchAttractions(props.city, keyword)
}

/** 美食搜索:交给美食 store,切换为餐厅结果模式。 */
function handleFoodSearch(keyword) {
  foodStore.searchFoodRestaurants(props.city, keyword)
}

/**
 * 城市切换时复位当前 Tab。
 *
 * 两个 Tab 组件内部监听 city.adcode 自行清空搜索词,这里只负责把
 * 默认 Tab 拉回"景点"。
 */
function resetCurrentTab() {
  activeTab.value = ATTRACTIONS_TAB
}

watch(
  () => props.city?.adcode,
  () => {
    resetCurrentTab()
  },
)
</script>

<style scoped>
.tm-city-workspace {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.tm-city-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
  padding-right: 4px;
}

.tm-city-welcome {
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
  height: 100%;
  padding: 40px 8px;
}

.tm-city-welcome-hint {
  margin: 0;
  font-size: 14px;
  color: var(--tm-muted);
}

.tm-hero-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--tm-primary-dark);
}

.tm-ai-column {
  height: 100%;
  min-height: 0;
  padding-left: 4px;
  overflow: auto;
}
</style>
