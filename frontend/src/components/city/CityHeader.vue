<template>
  <header class="tm-city-header">
    <div class="tm-city-header-main">
      <h2 class="tm-city-title">{{ displayOrUnknown(cityTitle) }}</h2>

      <p class="tm-weather-summary">
        <el-icon class="tm-weather-icon"><Sunny /></el-icon>
        <span class="tm-weather-summary-text">{{ summaryText }}</span>
      </p>

      <p v-if="metaText" class="tm-weather-meta">{{ metaText }}</p>

      <ClothingAdvice :text="clothingAdvice" />
    </div>

    <el-button
      class="tm-weather-refresh"
      text
      :loading="loading"
      title="刷新天气"
      @click="refreshWeather"
    >
      <el-icon v-if="!loading"><Refresh /></el-icon>
      <span v-else class="tm-weather-refresh-text">刷新中</span>
    </el-button>
  </header>
</template>

<script setup>
import { Refresh, Sunny } from '@element-plus/icons-vue'
import { computed } from 'vue'

import { displayOrUnknown, UNKNOWN_TEXT } from '../../utils/display'
import { useCityStore } from '../../stores/city'
import ClothingAdvice from './ClothingAdvice.vue'

/**
 * 城市顶部信息:城市名 · 省份 + 天气 + 穿衣建议。
 *
 * 始终显示在景点 / 美食 Tab 上方,不随 Tab 切换消失。
 */
const props = defineProps({
  city: { type: Object, default: null },
  weather: { type: Object, default: null },
  clothingAdvice: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

const cityStore = useCityStore()

/** "成都 · 四川"。 */
const cityTitle = computed(() => {
  const parts = [props.city?.city_name, props.city?.province].filter(
    (part) => typeof part === 'string' && part.trim(),
  )
  return parts.length ? parts.join(' · ') : ''
})

/** 温度:没有 temperature 时留空,让摘要整体兜底。 */
const temperatureText = computed(() => {
  const value = Number(props.weather?.temperature)
  return Number.isFinite(value) && props.weather?.temperature !== null && props.weather?.temperature !== ''
    ? `${value}°C`
    : ''
})

/** 温度区间:例如 18~25°C。 */
const temperatureRangeText = computed(() => {
  const min = Number(props.weather?.min_temperature)
  const max = Number(props.weather?.max_temperature)
  const hasMin = Number.isFinite(min) && props.weather?.min_temperature !== null
  const hasMax = Number.isFinite(max) && props.weather?.max_temperature !== null

  if (hasMin && hasMax) {
    return `${min}~${max}°C`
  }
  if (hasMax) {
    return `${max}°C`
  }
  if (hasMin) {
    return `${min}°C`
  }
  return ''
})

/** "22°C · 多云 · 18~25°C";全部缺失时显示"暂无信息"。 */
const summaryText = computed(() => {
  const parts = [temperatureText.value, props.weather?.weather, temperatureRangeText.value].filter(
    (part) => typeof part === 'string' && part.trim(),
  )
  return parts.length ? parts.join(' · ') : UNKNOWN_TEXT
})

/** 湿度 / 风向风力,有值才显示(§36:API 有值就显示)。 */
const metaText = computed(() => {
  const humidity = props.weather?.humidity
  const windDirection = props.weather?.wind_direction
  const windPower = props.weather?.wind_power
  const parts = []

  if (humidity !== null && humidity !== undefined && humidity !== '') {
    parts.push(`湿度 ${humidity}%`)
  }
  if (windDirection || windPower) {
    const wind = [windDirection, windPower ? `${windPower} 级` : ''].filter(Boolean).join(' ')
    parts.push(wind)
  }

  return parts.join(' · ')
})

/** 手动刷新当前城市天气。 */
function refreshWeather() {
  cityStore.loadWeatherForSelectedCity()
}
</script>

<style scoped>
.tm-city-header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 16px 18px;
  background: linear-gradient(135deg, var(--tm-primary-soft) 0%, #ffffff 72%);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius-lg);
}

.tm-city-header-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.tm-city-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--tm-primary-dark);
}

.tm-weather-summary {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0;
  font-size: 15px;
  color: var(--tm-ink);
}

.tm-weather-icon {
  color: var(--tm-accent);
}

.tm-weather-meta {
  margin: 0;
  font-size: 12px;
  color: var(--tm-muted);
}

.tm-weather-refresh {
  flex: none;
  font-size: 16px;
  color: var(--tm-primary);
}

.tm-weather-refresh-text {
  font-size: 12px;
}
</style>
