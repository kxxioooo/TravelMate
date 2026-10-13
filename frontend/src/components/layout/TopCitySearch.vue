<template>
  <div class="tm-topbar-inner">
    <el-autocomplete
      v-model="keyword"
      class="tm-city-search"
      :fetch-suggestions="refreshResults"
      :trigger-on-focus="false"
      placeholder="搜索城市(支持中文 / 拼音)"
      clearable
      @input="handleInput"
      @select="handleSelect"
      @clear="clearSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>

      <template #default="{ item }">
        <div class="tm-city-option">
          <span class="tm-city-option-name">{{ item.city_name }}</span>
          <span class="tm-city-option-meta">{{ item.province }} · {{ item.pinyin }}</span>
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
import { ref } from 'vue'

import cities from '../../data/cities.json'
import { searchCities } from '../../utils/citySearch'

defineProps({
  selectedCity: { type: Object, default: null },
})

const emit = defineEmits(['city-selected'])

const keyword = ref('')

/** 更新关键词。 */
function handleInput(value) {
  keyword.value = value ?? ''
}

/** 调用 searchCities() 得到候选项,交给 el-autocomplete 渲染。 */
function refreshResults(queryString, callback) {
  callback(searchCities(cities, queryString, 10))
}

/** 选中城市后向上抛出,并把输入框回填成城市名。 */
function handleSelect(city) {
  keyword.value = city.city_name
  emit('city-selected', city)
}

/** 清空搜索框。v0.1 不显示历史,v0.2 在这里增加 Recent Searches。 */
function clearSearch() {
  keyword.value = ''
}
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

@media (max-width: 640px) {
  .tm-city-search {
    width: 100%;
  }
}
</style>
