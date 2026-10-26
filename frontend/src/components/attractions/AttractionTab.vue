<template>
  <section class="tm-attraction-tab">
    <div class="tm-tab-toolbar">
      <el-input
        v-model="keyword"
        class="tm-attraction-search"
        :placeholder="t('attraction.search_placeholder')"
        clearable
        @keyup.enter="submitSearch"
        @clear="resetToDefault"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-button class="tm-attraction-search-btn" type="primary" @click="submitSearch">
        {{ t('attraction.search_button') }}
      </el-button>
      <el-button v-if="isSearchMode" text @click="resetToDefault">
        {{ t('attraction.back_to_default') }}
      </el-button>
    </div>

    <p v-if="isSearchMode" class="tm-attraction-mode-hint">
      {{
        t('attraction.search_hint', {
          keyword: displayOrUnknown(attractionStore.keyword),
          count: attractionStore.items.length,
        })
      }}
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
        :title="emptyTitle"
        :description="emptyDescription"
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
import { useI18n } from 'vue-i18n'

import { useAttractionStore } from '../../stores/attractions'
import { displayOrUnknown } from '../../utils/display'
import { formatLocalizedError } from '../../utils/i18nDisplay'
import EmptyState from '../common/EmptyState.vue'
import LoadMoreButton from '../common/LoadMoreButton.vue'
import AttractionCard from './AttractionCard.vue'

/**
 * 景点 Tab。
 *
 * 默认最多 10 个;关键词搜索时切换为搜索模式(page_size=20)并支持 Load More。
 * 英文关键词由后端转成中文关键词查高德,前端只负责保留用户输入的原文。
 */
const props = defineProps({
  city: { type: Object, default: null },
  active: { type: Boolean, default: false },
})

const emit = defineEmits(['search'])

const { t } = useI18n()

const attractionStore = useAttractionStore()

const keyword = ref('')
/** 本次挂载是否已经自动补过一次默认景点,避免重复请求。 */
const requested = ref(false)

const isSearchMode = computed(() => attractionStore.mode === 'search')

const emptyTitle = computed(() =>
  isSearchMode.value ? t('attraction.empty_search_title') : t('attraction.empty_default_title'),
)

/**
 * 空态描述。
 *
 * 后端 / 网络失败时显示本地化错误(按 error_code > detail > 状态码解析),
 * 只是"真的没有数据"时显示当前语言的引导文案 —— 两者绝不混为一谈。
 */
const emptyDescription = computed(() => {
  if (attractionStore.error) {
    return formatLocalizedError(attractionStore.error, {
      t,
      fallbackKey: isSearchMode.value
        ? 'attraction.empty_search_desc'
        : 'attraction.empty_default_desc',
    })
  }

  return isSearchMode.value ? t('attraction.empty_search_desc') : t('attraction.empty_default_desc')
})

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
