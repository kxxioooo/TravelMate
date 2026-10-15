<template>
  <div class="tm-topbar-inner">
    <el-autocomplete
      ref="autocompleteRef"
      v-model="keyword"
      class="tm-city-search"
      :fetch-suggestions="refreshResults"
      placeholder="搜索城市(支持中文 / 拼音)"
      clearable
      @input="handleInput"
      @focus="loadRecentSearches"
      @select="handleSelect"
      @clear="clearSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>

      <template #default="{ item }">
        <div
          class="tm-city-option"
          :class="item.source === 'recent' ? 'tm-suggestion-recent' : 'tm-suggestion-city'"
        >
          <span class="tm-city-option-name">{{ item.city_name }}</span>
          <span class="tm-city-option-meta">
            {{
              item.source === 'recent'
                ? `最近搜索${item.province ? ` · ${item.province}` : ''}`
                : `${item.province} · ${item.pinyin}`
            }}
          </span>
        </div>
      </template>
    </el-autocomplete>

    <el-tag v-if="selectedCity" type="success" effect="light" size="large" round>
      已选择:{{ selectedCity.city_name }} · {{ selectedCity.province }}
    </el-tag>
    <span v-else class="tm-topbar-hint">搜索并选择一个城市</span>
  </div>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'

import cities from '../../data/cities.json'
import { useCityStore } from '../../stores/city'
import { searchCities } from '../../utils/citySearch'

/** 给 el-autocomplete 的候选项补上 value 和来源标记(source 决定 UI 类名)。 */
function buildSuggestion(city, source) {
  const cityName = String(city?.city_name ?? '')

  return {
    city_name: cityName,
    province: city?.province ?? '',
    pinyin: city?.pinyin ?? '',
    adcode: city?.adcode ?? '',
    value: cityName,
    source,
  }
}

defineProps({
  selectedCity: { type: Object, default: null },
})

const emit = defineEmits(['city-selected'])

const cityStore = useCityStore()

const keyword = ref('')
const autocompleteRef = ref(null)

/** 最近搜索:来自后端,按当前登录用户过滤。 */
const recentSuggestions = computed(() =>
  cityStore.recentCities.map((city) => buildSuggestion(city, 'recent')),
)

/** 更新关键词。 */
function handleInput(value) {
  keyword.value = value ?? ''
}

/**
 * 下拉候选:
 *   keyword 为空 -> Recent Searches
 *   keyword 非空 -> 本地 cities.json 匹配
 *
 * el-autocomplete 在 focus 时会用当前(可能为空的)modelValue 触发一次,
 * 因此"空关键词 + focus"天然会走到 Recent Searches 分支。
 */
function refreshResults(queryString, callback) {
  const query = String(queryString ?? '').trim()

  if (!query) {
    callback(recentSuggestions.value)
    return
  }

  callback(searchCities(cities, query, 10).map((city) => buildSuggestion(city, 'city')))
}

/**
 * 拉取最近搜索。
 *
 * focus / mounted 都会调用;拉完后如果输入框仍为空,主动刷新一次下拉,
 * 避免"focus 已经触发过查询、历史却刚到"的时序竞争。
 */
async function loadRecentSearches() {
  try {
    await cityStore.loadRecentCities()
  } catch {
    // Recent Searches 是便利功能,失败不打扰用户。
  }

  if (!keyword.value) {
    autocompleteRef.value?.getData?.('')
  }
}

/**
 * 选中城市:向上抛出,并清空输入框。
 *
 * 真正写 history 由 cityStore.openCity() 完成,组件不承担数据写入。
 */
function handleSelect(city) {
  emit('city-selected', city)
  keyword.value = ''
}

/** 清空搜索框,并立刻显示 Recent Searches。 */
function clearSearch() {
  keyword.value = ''

  // el-autocomplete 清空时会把内部 activated 置为 false,
  // 这里显式重新激活下拉,让"清空后"立刻能看到最近搜索。
  if (autocompleteRef.value) {
    autocompleteRef.value.activated = true
    autocompleteRef.value.getData?.('')
  }
}

onMounted(() => {
  // 提前把历史预热好,用户第一次 focus 时不会闪空下拉。
  loadRecentSearches()
})
</script>

<style scoped>
.tm-topbar-inner {
  display: flex;
  gap: 16px;
  align-items: center;
  width: 100%;
}

.tm-city-search {
  width: 320px;
}

.tm-topbar-hint {
  font-size: 13px;
  color: var(--tm-muted);
}

.tm-city-option {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  width: 100%;
  gap: 16px;
}

.tm-city-option-name {
  font-size: 14px;
  color: var(--tm-ink);
}

.tm-city-option-meta {
  font-size: 12px;
  color: var(--tm-muted);
}

.tm-suggestion-recent .tm-city-option-name::before {
  margin-right: 6px;
  font-size: 12px;
  color: var(--tm-muted);
  content: '🕘';
}

@media (max-width: 640px) {
  .tm-city-search {
    width: 100%;
  }
}
</style>
