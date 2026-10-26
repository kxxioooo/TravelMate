import { defineStore } from 'pinia'

import { getFeaturedFoods, getRestaurantDetail, searchFoodRestaurants } from '../api/food'
import { toErrorInfo } from '../api/http'

/** 搜索模式每页数量(§12:pageSize = 20)。 */
const SEARCH_PAGE_SIZE = 20

/** 每种代表性美食最多展示 2 家餐厅(§1 第 16 条)。 */
const MAX_RESTAURANTS_PER_FOOD = 2

/** 城市对象 -> 只保留请求需要的两个字段(中文名 + adcode)。 */
function normalizeCity(city) {
  if (!city || !city.city_name) {
    return null
  }

  return { city_name: city.city_name, adcode: city.adcode ?? null }
}

/** 可选英文字段:没有就空字符串,绝不伪造译文。 */
function optionalText(value) {
  return typeof value === 'string' ? value.trim() : ''
}

/** 列表接口的一行 -> 组件可安全渲染的餐厅摘要(UI 只显示名称 + 详情)。 */
function normalizeRestaurant(item) {
  if (!item || typeof item !== 'object') {
    return null
  }

  const poiId = item.poi_id ?? item.id
  if (poiId === null || poiId === undefined || poiId === '') {
    return null
  }

  return {
    poi_id: String(poiId),
    name: typeof item.name === 'string' ? item.name : '',
    name_en: optionalText(item.name_en),
    name_en_source: optionalText(item.name_en_source),
  }
}

/** 十大美食响应 -> 组件可安全渲染的结构(含双语字段)。 */
function normalizeFood(item) {
  if (!item || typeof item !== 'object') {
    return null
  }

  const name = typeof item.name === 'string' ? item.name.trim() : ''
  if (!name) {
    return null
  }

  return {
    name,
    name_en: optionalText(item.name_en),
    description: typeof item.description === 'string' ? item.description : '',
    description_en: optionalText(item.description_en),
    cover_photo: typeof item.cover_photo === 'string' ? item.cover_photo : '',
    representative_restaurants: (Array.isArray(item.representative_restaurants)
      ? item.representative_restaurants
      : []
    )
      .map(normalizeRestaurant)
      .filter(Boolean)
      .slice(0, MAX_RESTAURANTS_PER_FOOD),
  }
}

/** 分页响应 -> { items, hasMore }。 */
function normalizeRestaurantPage(data) {
  const rawItems = Array.isArray(data?.items) ? data.items : []
  return {
    items: rawItems.map(normalizeRestaurant).filter(Boolean),
    hasMore: Boolean(data?.has_more),
  }
}

/** 追加分页结果时按 poi_id 去重。 */
function mergeUnique(existing, incoming) {
  const seen = new Set(existing.map((item) => item.poi_id))
  return [...existing, ...incoming.filter((item) => !seen.has(item.poi_id))]
}

/**
 * 美食状态中心:十大美食(featured)与餐厅搜索(search)两种模式。
 *
 * v0.3.1:双语字段随响应一起缓存,切换语言只重新格式化,不重新请求,
 * 因此搜索模式的分页与已加载列表都不会被语言切换重置。
 */
export const useFoodStore = defineStore('food', {
  state: () => ({
    featuredFoods: [],
    restaurantResults: [],
    mode: 'featured',
    keyword: '',
    page: 1,
    pageSize: SEARCH_PAGE_SIZE,
    hasMore: false,
    selectedRestaurant: null,
    isLoading: false,
    isDetailLoading: false,
    error: null,
  }),

  actions: {
    /** 十大代表性美食:每种最多 2 家代表餐厅。 */
    async loadFeaturedFoods(city) {
      const target = normalizeCity(city)
      if (!target) {
        this.resetFoodState()
        return
      }

      this.mode = 'featured'
      this.keyword = ''
      this.page = 1
      this.hasMore = false
      this.error = null
      this.restaurantResults = []
      this.featuredFoods = []
      this.isLoading = true

      try {
        const data = await getFeaturedFoods(target)
        const rawItems = Array.isArray(data?.items) ? data.items : []
        this.featuredFoods = rawItems.map(normalizeFood).filter(Boolean)
      } catch (error) {
        this.featuredFoods = []
        this.error = toErrorInfo(error)
      } finally {
        this.isLoading = false
      }
    },

    /** 关键词搜索餐厅;空关键词回到 featured 模式。 */
    async searchFoodRestaurants(city, keyword) {
      const query = String(keyword ?? '').trim()
      if (!query) {
        return this.loadFeaturedFoods(city)
      }

      const target = normalizeCity(city)
      if (!target) {
        this.resetFoodState()
        return
      }

      this.mode = 'search'
      this.keyword = query
      this.page = 1
      this.pageSize = SEARCH_PAGE_SIZE
      this.hasMore = false
      this.error = null
      this.restaurantResults = []
      this.isLoading = true

      try {
        const data = await searchFoodRestaurants({
          city_name: target.city_name,
          adcode: target.adcode,
          keyword: query,
          page: 1,
          page_size: SEARCH_PAGE_SIZE,
        })

        const page = normalizeRestaurantPage(data)
        this.restaurantResults = page.items
        this.hasMore = page.hasMore
      } catch (error) {
        this.restaurantResults = []
        this.hasMore = false
        this.error = toErrorInfo(error)
      } finally {
        this.isLoading = false
      }
    },

    /** 餐厅结果翻页;失败时把页码恢复,避免跳过一页。 */
    async loadMoreRestaurants(city) {
      const target = normalizeCity(city)
      if (!target || this.mode !== 'search' || !this.hasMore || this.isLoading) {
        return
      }

      const previousPage = this.page
      const nextPage = previousPage + 1

      this.page = nextPage
      this.error = null
      this.isLoading = true

      try {
        const data = await searchFoodRestaurants({
          city_name: target.city_name,
          adcode: target.adcode,
          keyword: this.keyword,
          page: nextPage,
          page_size: this.pageSize,
        })

        const page = normalizeRestaurantPage(data)
        this.restaurantResults = mergeUnique(this.restaurantResults, page.items)
        this.hasMore = page.hasMore
      } catch (error) {
        this.page = previousPage
        this.error = toErrorInfo(error)
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 打开餐厅详情。
     *
     * 同样先放占位对象:接口异常时弹窗依旧能打开并显示"暂无信息"。
     */
    async openRestaurantDetail(poiId) {
      const id = poiId === null || poiId === undefined ? '' : String(poiId)
      if (!id) {
        return
      }

      this.error = null
      this.isDetailLoading = true
      this.selectedRestaurant = {
        poi_id: id,
        name: '',
        name_en: '',
        cost: null,
        address: null,
        address_en: '',
        rating: null,
        telephone: null,
        photos: [],
      }

      try {
        const data = await getRestaurantDetail(id)
        const rating = Number(data?.rating)
        const hasRating = data?.rating !== null && data?.rating !== '' && Number.isFinite(rating) && rating > 0

        this.selectedRestaurant = {
          poi_id: data?.poi_id === null || data?.poi_id === undefined ? id : String(data.poi_id),
          name: typeof data?.name === 'string' ? data.name : '',
          name_en: optionalText(data?.name_en),
          name_en_source: optionalText(data?.name_en_source),
          cost: data?.cost ?? null,
          address: data?.address ?? null,
          address_en: optionalText(data?.address_en),
          rating: hasRating ? rating : null,
          telephone: data?.telephone ?? null,
          photos: Array.isArray(data?.photos) ? data.photos : [],
        }
      } catch (error) {
        this.error = toErrorInfo(error)
      } finally {
        this.isDetailLoading = false
      }
    },

    /** 关闭餐厅详情弹窗。 */
    closeRestaurantDetail() {
      this.selectedRestaurant = null
    },

    /** 切换城市 / 退出登录时清空旧城市美食状态。 */
    resetFoodState() {
      this.featuredFoods = []
      this.restaurantResults = []
      this.mode = 'featured'
      this.keyword = ''
      this.page = 1
      this.pageSize = SEARCH_PAGE_SIZE
      this.hasMore = false
      this.selectedRestaurant = null
      this.isLoading = false
      this.isDetailLoading = false
      this.error = null
    },
  },
})
