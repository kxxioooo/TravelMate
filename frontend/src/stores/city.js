import { defineStore } from 'pinia'

import { getRecentCities, recordCityView } from '../api/city'
import { getWeather } from '../api/weather'

/**
 * 读取统一的失败文案。
 *
 * api/http.js 的拦截器已经把 detail 归一化成 error.normalized.message,
 * 这里只在极端情况下才回退到默认文案,保证界面不会出现 Traceback。
 */
function resolveErrorMessage(error, fallback) {
  return error?.normalized?.message ?? error?.message ?? fallback
}

/**
 * 当前城市上下文:选中城市 + 实时天气 + 穿衣建议 + 最近搜索。
 *
 * 选城市只有 `openCity()` 一个入口,页面组件不自己拼 API。
 */
export const useCityStore = defineStore('city', {
  state: () => ({
    selectedCity: null,
    recentCities: [],
    weather: null,
    clothingAdvice: '',
    isWeatherLoading: false,
    error: '',
  }),

  actions: {
    /**
     * 只修改当前城市对象本身 —— 这里刻意不发任何网络请求,
     * 所有请求都由 `openCity()` / `loadWeatherForSelectedCity()` 负责。
     */
    setSelectedCity(city) {
      if (!city || !city.city_name) {
        this.selectedCity = null
        return
      }

      this.selectedCity = { ...city }
    },

    /**
     * 用户选中一个城市后的统一入口。
     *
     * 1. 记录浏览历史 与 拉取天气 并行执行(§3 用户流程:并行获取);
     * 2. 完成后刷新 Recent Searches。
     *
     * 注意:这里不加载十大美食 —— 默认 Tab 是景点,美食等用户第一次
     * 切到"美食" Tab 再加载。
     */
    async openCity(city) {
      this.setSelectedCity(city)

      if (!this.selectedCity) {
        this.weather = null
        this.clothingAdvice = ''
        return null
      }

      this.error = ''

      const recordTask = recordCityView(this.selectedCity).catch((error) => {
        this.error = resolveErrorMessage(error, '城市浏览记录写入失败')
        return null
      })

      await Promise.all([recordTask, this.loadWeatherForSelectedCity()])
      await this.loadRecentCities()

      return this.selectedCity
    },

    /** 拉取 Recent Searches;失败时静默降级为空列表,不影响主流程。 */
    async loadRecentCities() {
      try {
        const data = await getRecentCities()
        this.recentCities = Array.isArray(data) ? data.filter((item) => item && item.city_name) : []
      } catch {
        this.recentCities = []
      }

      return this.recentCities
    },

    /** 拉取当前城市天气与穿衣建议;没有选中城市时直接返回。 */
    async loadWeatherForSelectedCity() {
      const city = this.selectedCity
      if (!city) {
        return null
      }

      this.error = ''
      // 先清空旧城市天气,避免切换城市时短暂显示上一个城市的数据。
      this.weather = null
      this.clothingAdvice = ''
      this.isWeatherLoading = true

      try {
        const data = await getWeather(city.adcode)
        this.weather = data?.weather ?? null
        this.clothingAdvice = typeof data?.clothing_advice === 'string' ? data.clothing_advice : ''
        return data
      } catch (error) {
        this.weather = null
        this.clothingAdvice = ''
        this.error = resolveErrorMessage(error, '天气获取失败')
        return null
      } finally {
        this.isWeatherLoading = false
      }
    },

    /** 退出登录 / 切换账号时清空城市上下文。 */
    resetCityContext() {
      this.selectedCity = null
      this.recentCities = []
      this.weather = null
      this.clothingAdvice = ''
      this.isWeatherLoading = false
      this.error = ''
    },
  },
})
