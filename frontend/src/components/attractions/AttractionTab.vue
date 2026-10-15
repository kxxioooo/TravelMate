<template>
  <section class="tm-attraction-tab">
    <div class="tm-tab-toolbar">
      <el-input
        v-model="keyword"
        class="tm-attraction-search"
        placeholder="搜索当前城市的景点,例如:古镇"
        clearable
        @keyup.enter="submitSearch"
        @clear="resetToDefault"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-button class="tm-attraction-search-btn" type="primary" @click="submitSearch">
        搜索
      </el-button>
      <el-button v-if="isSearchMode" text @click="resetToDefault">返回默认</el-button>
    </div>

    <p v-if="isSearchMode" class="tm-attraction-mode-hint">
      「{{ displayOrUnknown(attractionStore.keyword) }}」的搜索结果,共
      {{ attractionStore.items.length }} 个已加载
    </p>

    <div v-loading="attractionStore.isLoading" class="tm-attraction-list">
      <div v-if="attractionStore.items.length" class="tm-card-grid">
        <AttractionCard
          v-for="item in attractionStore.items"
          :key="item.poi_id"
          :attraction="item"
          @open-detail="openAttractionDetail"
        />
      </div>

      <EmptyState
        v-else-if="!attractionStore.isLoading"
        :title="isSearchMode ? '没有找到相关景点' : '暂无景点数据'"
        :description="attractionStore.error || emptyDescription"
      />
    </div>

    <LoadMoreButton
      v-if="isSearchMode && attractionStore.hasMore"
      :loading="attractionStore.isLoading"
      @load-more="loadMore"
    />
  </section>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'
import { computed, ref, watch } from 'vue'

import { useAttractionStore } from '../../stores/attractions'
import { displayOrUnknown } from '../../utils/display'
import EmptyState from '../common/EmptyState.vue'
import LoadMoreButton from '../common/LoadMoreButton.vue'
import AttractionCard from './AttractionCard.vue'

/**
 * 景点 Tab。
 *
 * 默认最多 10 个;关键词搜索时切换为搜索模式(page_size=20)并支持 Load More。
 */
const props = defineProps({
  city: { type: Object, default: null },
  active: { type: Boolean, default: false },
})

const emit = defineEmits(['search'])

const attractionStore = useAttractionStore()

const keyword = ref('')
/** 本次挂载是否已经自动补过一次默认景点,避免重复请求。 */
const requested = ref(false)

const isSearchMode = computed(() => attractionStore.mode === 'search')

const emptyDescription = computed(() =>
  isSearchMode.value
    ? '换一个关键词试试,或点击「返回默认」查看默认推荐景点。'
    : '当前城市暂时没有可展示的景点数据,请稍后重试。',
)

/** 列表为空时的兜底:补一次默认 10 景点。 */
function ensureDefaultLoaded() {
  if (requested.value) {
    return
  }
  // 用户正在看搜索结果时,不要用默认 Top 10 把结果覆盖掉。
  if (attractionStore.mode === 'search') {
    return
  }
  if (attractionStore.items.length > 0 || attractionStore.isLoading) {
    return
  }

  requested.value = true
  attractionStore.loadDefaultAttractions(props.city)
}

/** 提交搜索:空关键词回到默认 Top 10,非空进入搜索模式。 */
function submitSearch() {
  const value = keyword.value.trim()
  if (!value) {
    resetToDefault()
    return
  }

  emit('search', value)
}

/** 只在搜索模式 + hasMore 时翻页。 */
function loadMore() {
  if (!isSearchMode.value || !attractionStore.hasMore || attractionStore.isLoading) {
    return
  }

  attractionStore.loadMore(props.city)
}

/** 清空搜索词并恢复默认 Top 10。 */
function resetToDefault() {
  keyword.value = ''
  requested.value = true
  attractionStore.loadDefaultAttractions(props.city)
}

/** 打开详情:交给 store,弹窗由 CityWorkspace 承载。 */
function openAttractionDetail(poiId) {
  attractionStore.openDetail(poiId)
}

watch(
  () => props.active,
  (isActive) => {
    if (isActive) {
      ensureDefaultLoaded()
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
.tm-attraction-tab {
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

.tm-attraction-search {
  width: 320px;
  max-width: 100%;
}

.tm-attraction-mode-hint {
  margin: 0;
  font-size: 12px;
  color: var(--tm-muted);
}

.tm-attraction-list {
  min-height: 160px;
}

@media (max-width: 900px) {
  .tm-attraction-search {
    width: 100%;
  }
}
</style>
