import { defineStore } from 'pinia'

import { getRecentCities, recordCityView } from '../api/city'
import { toErrorInfo } from '../api/http'
import { getWeather } from '../api/weather'

/**
 * 当前城市上下文:选中城市 + 实时天气 + 穿衣建议 + 最近搜索。
 *
 * 选城市只有 `openCity()` 一个入口,页面组件不自己拼 API。
 *
 * v0.3.1:错误不再保存"已经翻译好的句子",而是保存
 * `{ status, errorCode, key, detail }`,渲染时按当时的语言解析 ——
 * 这样切换语言后旧错误也会跟着换语言,不会残留上一门语言的中文。
 */
export const useCityStore = defineStore('city', {
  state: () => ({
    selectedCity: null,
    recentCities: [],
    weather: null,
    /** 原始穿衣建议文本:仅在缺 `clothing_advice_codes` 时兜底显示。 */
    clothingAdvice: '',
    /** 语言无关穿衣建议枚举(契约 §3)。 */
    clothingAdviceCodes: [],
    isWeatherLoading: false,
    error: null,
  }),

  actions: {
    /**
     * 只修改当前城市对象本身 —— 这里刻意不发任何网络请求,
     * 所有请求都由 `openCity()` / `loadWeatherForSelectedCity()` 负责。
     *
     * 城市对象同时携带中文 `city_name` / `province` 与展示用英文名,
     * 请求参数永远只取中文名 + adcode。
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
     * 1. 记录浏览历史 与 拉取天气 并行执行;
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
        this.clothingAdviceCodes = []
        return null
      }

      this.error = null

      const recordTask = recordCityView(this.selectedCity).catch((error) => {
        this.error = toErrorInfo(error)
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

      this.error = null
      // 先清空旧城市天气,避免切换城市时短暂显示上一个城市的数据。
      this.weather = null
      this.clothingAdvice = ''
      this.clothingAdviceCodes = []
      this.isWeatherLoading = true

      try {
        const data = await getWeather(city.adcode)
        this.weather = data?.weather ?? null
        this.clothingAdvice = typeof data?.clothing_advice === 'string' ? data.clothing_advice : ''
        this.clothingAdviceCodes = Array.isArray(data?.clothing_advice_codes)
          ? data.clothing_advice_codes.filter((code) => typeof code === 'string' && code.trim())
          : []
        return data
      } catch (error) {
        this.weather = null
        this.clothingAdvice = ''
        this.clothingAdviceCodes = []
        this.error = toErrorInfo(error)
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
      this.clothingAdviceCodes = []
      this.isWeatherLoading = false
      this.error = null
    },
  },
})
