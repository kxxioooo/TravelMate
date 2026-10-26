<template>
  <div class="tm-topbar-inner">
    <el-autocomplete
      ref="autocompleteRef"
      v-model="keyword"
      class="tm-city-search"
      :fetch-suggestions="refreshResults"
      :placeholder="t('city.search_placeholder')"
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
          <!-- 英文模式 `Chengdu (成都)`,中文模式 `成都`;业务值始终是中文名 + adcode -->
          <span class="tm-city-option-name">{{ optionName(item) }}</span>
          <span class="tm-city-option-meta">{{ optionMeta(item) }}</span>
        </div>
      </template>
    </el-autocomplete>

    <el-tag v-if="selectedCity" type="success" effect="light" size="large" round>
      {{ t('city.selected_tag', { city: displayCityLabel(selectedCity, locale) }) }}
    </el-tag>
    <span v-else class="tm-topbar-hint">{{ t('city.select_hint') }}</span>
  </div>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import cities from '../../data/cities.json'
import { useCityStore } from '../../stores/city'
import { searchCities } from '../../utils/citySearch'
import {
  displayBilingualName,
  displayCityLabel,
  displayProvinceName,
} from '../../utils/i18nDisplay'
import { enrichCity } from '../../utils/localeSearch'

/**
 * 给 el-autocomplete 的候选项补上 value 和来源标记(source 决定 UI 类名)。
 *
 * `city_name` / `province` / `adcode` 保持后端可用的原值;
 * `city_name_en` / `province_en` 只用于展示,不会被写进任何请求参数。
 */
function buildSuggestion(city, source) {
  const enriched = enrichCity(city) ?? {}

  return {
    city_name: String(enriched.city_name ?? ''),
    city_name_en: String(enriched.city_name_en ?? ''),
    province: String(enriched.province ?? ''),
    province_en: String(enriched.province_en ?? ''),
    pinyin: String(enriched.pinyin ?? ''),
    pinyin_initials: String(enriched.pinyin_initials ?? ''),
    aliases_en: Array.isArray(enriched.aliases_en) ? enriched.aliases_en : [],
    adcode: enriched.adcode ?? '',
    value: String(enriched.city_name ?? ''),
    source,
  }
}

defineProps({
  selectedCity: { type: Object, default: null },
})

const emit = defineEmits(['city-selected'])

const { t, locale } = useI18n()

const cityStore = useCityStore()

const keyword = ref('')
const autocompleteRef = ref(null)

/** 最近搜索:来自后端(只存中文名 + adcode),英文名按 adcode 从本地索引补齐。 */
const recentSuggestions = computed(() =>
  cityStore.recentCities.map((city) => buildSuggestion(city, 'recent')),
)

/** 候选主标题:`Chengdu (成都)` / `成都`。 */
function optionName(item) {
  return displayBilingualName(item.city_name, item.city_name_en, locale.value)
}

/**
 * 候选副标题:
 *   中文模式 -> `四川 · chengdu`
 *   英文模式 -> `Sichuan (四川)`
 *   最近搜索 -> 前缀 `最近搜索 / Recent`
 */
function optionMeta(item) {
  const province = displayProvinceName(item, locale.value)

  if (item.source === 'recent') {
    return province
      ? `${t('city.recent_meta')} · ${province}`
      : t('city.recent_meta')
  }

  if (locale.value === 'en-US') {
    return province
  }

  return [item.province, item.pinyin].filter(Boolean).join(' · ')
}

/** 更新关键词(保留用户原文,不做任何改写)。 */
function handleInput(value) {
  keyword.value = value ?? ''
}

/**
 * 下拉候选:
 *   keyword 为空 -> Recent Searches
 *   keyword 非空 -> 本地 cities.json 多语言匹配(中文 / 拼音 / 首字母 / 英文 / 别名)
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
 * 抛出的对象只带中文名 / adcode / province 等业务字段,
 * 展示用的英文名不会被写进城市历史或 Conversation。
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
  flex: 1;
  gap: 16px;
  align-items: center;
  min-width: 0;
}

.tm-city-search {
  width: 320px;
  max-width: 100%;
}

.tm-topbar-hint {
  overflow: hidden;
  font-size: 13px;
  color: var(--tm-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
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
  white-space: nowrap;
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
