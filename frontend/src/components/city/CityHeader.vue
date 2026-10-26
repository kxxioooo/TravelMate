<template>
  <header class="tm-city-header">
    <div class="tm-city-header-main">
      <h2 class="tm-city-title">{{ displayOrUnknown(cityTitle) }}</h2>

      <p class="tm-weather-summary">
        <el-icon class="tm-weather-icon"><Sunny /></el-icon>
        <span class="tm-weather-summary-text">{{ summaryText }}</span>
      </p>

      <p v-if="metaText" class="tm-weather-meta">{{ metaText }}</p>

      <ClothingAdvice :text="clothingAdvice" :codes="clothingAdviceCodes" />
    </div>

    <el-button
      class="tm-weather-refresh"
      text
      :loading="loading"
      :title="t('city.weather_refresh')"
      :aria-label="t('city.weather_refresh')"
      @click="refreshWeather"
    >
      <el-icon v-if="!loading"><Refresh /></el-icon>
      <span v-else class="tm-weather-refresh-text">{{ t('city.weather_refreshing') }}</span>
    </el-button>
  </header>
</template>

<script setup>
import { Refresh, Sunny } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { resolveWeatherLabel, resolveWindDirectionLabel } from '../../constants/localizedTerms'
import { useCityStore } from '../../stores/city'
import { displayOrUnknown } from '../../utils/display'
import { displayCityLabel } from '../../utils/i18nDisplay'
import ClothingAdvice from './ClothingAdvice.vue'

/**
 * 城市顶部信息:城市名 · 省份 + 天气 + 穿衣建议。
 *
 * 始终显示在景点 / 美食 Tab 上方,不随 Tab 切换消失。
 * 英文模式下城市/省份按 `Chengdu (成都) · Sichuan (四川)` 展示;
 * 天气文案由 `weather_code` 决定(数字字段原样显示,不做任何换算)。
 */
const props = defineProps({
  city: { type: Object, default: null },
  weather: { type: Object, default: null },
  clothingAdvice: { type: String, default: '' },
  clothingAdviceCodes: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const { t, locale } = useI18n()

const cityStore = useCityStore()

/** `Chengdu (成都) · Sichuan (四川)` / `成都 · 四川`。 */
const cityTitle = computed(() => displayCityLabel(props.city, locale.value))

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

/**
 * `22°C · 多云 · 18~25°C`。
 *
 * 天气词用 `weather_code` 走本地化(缺失时按中文原文映射 code 兜底),
 * 所以英文模式下不会残留中文天气;全部缺失时显示当前语言"暂无信息"。
 */
const summaryText = computed(() => {
  const parts = [
    temperatureText.value,
    props.weather ? resolveWeatherLabel(props.weather, t) : '',
    temperatureRangeText.value,
  ].filter((part) => typeof part === 'string' && part.trim())

  return parts.length ? parts.join(' · ') : displayOrUnknown(null)
})

/**
 * 湿度 / 风向风力,有值才显示。
 *
 * 湿度、风力数字原样保留,只本地化单位与标签;风向按已审核映射翻译
 * (未收录的写法保持高德原始数据,不臆造)。
 */
const metaText = computed(() => {
  const humidity = props.weather?.humidity
  const windDirection = props.weather?.wind_direction
  const windPower = props.weather?.wind_power
  const parts = []

  if (humidity !== null && humidity !== undefined && humidity !== '') {
    parts.push(t('city.humidity', { value: humidity }))
  }

  if (windDirection || windPower) {
    const wind = [
      resolveWindDirectionLabel(windDirection, t, locale.value),
      windPower ? t('city.wind_power', { value: windPower }) : '',
    ]
      .filter(Boolean)
      .join(' ')
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
