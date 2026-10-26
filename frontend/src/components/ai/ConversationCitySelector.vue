<template>
  <div class="tm-city-selector">
    <el-input
      v-model="keyword"
      class="tm-conversation-city-search"
      :placeholder="t('conversation.city_search_placeholder')"
      clearable
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>

    <ul v-if="candidates.length" class="tm-city-options">
      <li v-for="city in candidates" :key="city.adcode">
        <button type="button" class="tm-city-option-item" @click="toggleCity(city)">
          <!-- 英文模式 `Chengdu (成都)` / `Sichuan (四川)`;命中值仍是中文名 + adcode -->
          <span class="tm-city-option-name">{{ optionName(city) }}</span>
          <span class="tm-city-option-meta">{{ optionMeta(city) }}</span>
        </button>
      </li>
    </ul>

    <div class="tm-city-chips">
      <span v-for="city in selectedCities" :key="city.adcode" class="tm-city-chip">
        <span class="tm-city-chip-name">{{ optionName(city) }}</span>
        <button
          type="button"
          class="tm-city-chip-remove"
          :aria-label="t('conversation.remove_city', { city: optionName(city) })"
          @click="removeCity(city.adcode)"
        >
          ×
        </button>
      </span>

      <span v-if="!selectedCities.length" class="tm-city-chips-hint">
        {{ t('conversation.chips_empty_hint') }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { Search } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import cities from '../../data/cities.json'
import { searchCities } from '../../utils/citySearch'
import { displayBilingualName, displayProvinceName } from '../../utils/i18nDisplay'
import { enrichCity } from '../../utils/localeSearch'

/** 搜索关键词由父组件(NewConversationDialog)持有,resetForm() 才能一并清空。 */
const keyword = defineModel('keyword', { type: String, default: '' })

const props = defineProps({
  selectedCities: { type: Array, default: () => [] },
})

const emit = defineEmits(['toggle-city', 'remove-city'])

const { t, locale } = useI18n()

/**
 * §21.1 复用 cities.json + searchCities(),不新建第二份城市数据。
 * 中文 / 中文片段 / 拼音 / 首字母 / 英文名 / 英文别名都能命中。
 */
function searchAvailableCities(value) {
  return searchCities(cities, value, 8)
}

const candidates = computed(() => searchAvailableCities(keyword.value))

/** 候选城市主标题:`Chengdu (成都)` / `成都`。 */
function optionName(city) {
  const enriched = enrichCity(city) ?? {}
  return displayBilingualName(enriched.city_name, enriched.city_name_en, locale.value) || t('common.unknown')
}

/** 候选城市副标题:省份(英文模式带括号中文)。 */
function optionMeta(city) {
  return displayProvinceName(city, locale.value)
}

/** §21.2 加入还是移除由父组件按 adcode 判断。 */
function toggleCity(city) {
  emit('toggle-city', city)
}

/** §21.3 移除已经选择的 Chip(整组替换仍由父组件完成)。 */
function removeCity(adcode) {
  const target = props.selectedCities.find((city) => String(city.adcode) === String(adcode))

  if (!target) {
    return
  }

  emit('remove-city', target)
}
</script>

<style scoped>
.tm-city-selector {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tm-city-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 180px;
  padding: 4px;
  margin: 0;
  overflow-y: auto;
  list-style: none;
  background: var(--tm-page-bg);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius);
}

.tm-city-option-item {
  display: flex;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
  width: 100%;
  padding: 8px 10px;
  font: inherit;
  font-size: 13.5px;
  color: var(--tm-ink);
  text-align: left;
  cursor: pointer;
  background: none;
  border: 0;
  border-radius: 8px;
}

.tm-city-option-item:hover {
  background: var(--tm-primary-soft);
}

.tm-city-option-meta {
  font-size: 12px;
  color: var(--tm-muted);
}

.tm-city-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  min-height: 30px;
}

.tm-city-chip {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 4px 6px 4px 10px;
  font-size: 13px;
  color: var(--tm-primary-dark);
  background: var(--tm-primary-soft);
  border-radius: 999px;
}

.tm-city-chip-remove {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  font: inherit;
  font-size: 13px;
  line-height: 1;
  color: var(--tm-primary-dark);
  cursor: pointer;
  background: rgba(255, 255, 255, 0.75);
  border: 0;
  border-radius: 50%;
}

.tm-city-chip-remove:hover {
  color: #fff;
  background: var(--tm-primary);
}

.tm-city-chips-hint {
  font-size: 12.5px;
  color: var(--tm-muted);
}
</style>
