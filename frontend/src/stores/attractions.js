import { defineStore } from 'pinia'

import { getAttractionDetail, getAttractions } from '../api/attractions'

/** 默认推荐景点数量(§1 第 10 条:默认显示 10 个)。 */
const DEFAULT_PAGE_SIZE = 10

/** 搜索模式每页数量(§11:搜索时 page_size = 20)。 */
const SEARCH_PAGE_SIZE = 20

/** 读取统一失败文案。 */
function resolveErrorMessage(error, fallback) {
  return error?.normalized?.message ?? error?.message ?? fallback
}

/** 只保留后端真实给的字段,任何缺失都保持 null / 空数组,绝不填假数据。 */
function normalizeTags(tags) {
  if (!Array.isArray(tags)) {
    return []
  }

  return tags.filter((tag) => typeof tag === 'string' && tag.trim()).map((tag) => tag.trim())
}

/** 列表接口的一行 -> 组件可安全渲染的景点摘要。 */
function normalizeAttraction(item) {
  if (!item || typeof item !== 'object') {
    return null
  }

  const poiId = item.poi_id ?? item.id
  if (poiId === null || poiId === undefined || poiId === '') {
    return null
  }

  const rating = Number(item.rating)
  const hasRating = item.rating !== null && item.rating !== '' && Number.isFinite(rating) && rating > 0

  return {
    poi_id: String(poiId),
    name: typeof item.name === 'string' ? item.name : '',
    cover_photo: typeof item.cover_photo === 'string' ? item.cover_photo : '',
    rating: hasRating ? rating : null,
    tags: normalizeTags(item.tags),
  }
}

/** 分页响应 -> { items, hasMore }。 */
function normalizePage(data) {
  const rawItems = Array.isArray(data?.items) ? data.items : []
  return {
    items: rawItems.map(normalizeAttraction).filter(Boolean),
    hasMore: Boolean(data?.has_more),
  }
}

/** 城市对象 -> 只保留请求需要的两个字段。 */
function normalizeCity(city) {
  if (!city || !city.city_name) {
    return null
  }

  return { city_name: city.city_name, adcode: city.adcode ?? null }
}

/** 追加分页结果时按 poi_id 去重,避免第三方接口翻页重复。 */
function mergeUnique(existing, incoming) {
  const seen = new Set(existing.map((item) => item.poi_id))
  return [...existing, ...incoming.filter((item) => !seen.has(item.poi_id))]
}

/** 景点状态中心:列表 / 搜索 / 分页 / 详情。 */
export const useAttractionStore = defineStore('attractions', {
  state: () => ({
    items: [],
    mode: 'default',
    keyword: '',
    page: 1,
    pageSize: SEARCH_PAGE_SIZE,
    hasMore: false,
    selectedDetail: null,
    isLoading: false,
    isDetailLoading: false,
    error: '',
  }),

  actions: {
    /** 默认 Top 10 景点:mode=default、keyword=""、page=1、page_size=10。 */
    async loadDefaultAttractions(city) {
      const target = normalizeCity(city)
      if (!target) {
        this.resetAttractions()
        return
      }

      this.mode = 'default'
      this.keyword = ''
      this.page = 1
      this.hasMore = false
      this.error = ''
      this.items = []
      this.isLoading = true

      try {
        const data = await getAttractions({
          city_name: target.city_name,
          adcode: target.adcode,
          page: 1,
          page_size: DEFAULT_PAGE_SIZE,
        })

        this.items = normalizePage(data).items
        // 默认模式固定只有 10 个,不提供 Load More。
        this.hasMore = false
      } catch (error) {
        this.items = []
        this.hasMore = false
        this.error = resolveErrorMessage(error, '景点加载失败,请稍后重试')
      } finally {
        this.isLoading = false
      }
    },

    /** 关键词搜索:mode=search、page=1、page_size=20,替换列表。 */
    async searchAttractions(city, keyword) {
      const query = String(keyword ?? '').trim()
      if (!query) {
        return this.loadDefaultAttractions(city)
      }

      const target = normalizeCity(city)
      if (!target) {
        this.resetAttractions()
        return
      }

      this.mode = 'search'
      this.keyword = query
      this.page = 1
      this.pageSize = SEARCH_PAGE_SIZE
      this.hasMore = false
      this.error = ''
      this.items = []
      this.isLoading = true

      try {
        const data = await getAttractions({
          city_name: target.city_name,
          adcode: target.adcode,
          keyword: query,
          page: 1,
          page_size: SEARCH_PAGE_SIZE,
        })

        const page = normalizePage(data)
        this.items = page.items
        this.hasMore = page.hasMore
      } catch (error) {
        this.items = []
        this.hasMore = false
        this.error = resolveErrorMessage(error, '景点搜索失败,请稍后重试')
      } finally {
        this.isLoading = false
      }
    },

    /** 只用于 search 模式的翻页;失败必须把页码恢复,否则下一页会被跳过。 */
    async loadMore(city) {
      const target = normalizeCity(city)
      if (!target || this.mode !== 'search' || !this.hasMore || this.isLoading) {
        return
      }

      const previousPage = this.page
      const nextPage = previousPage + 1

      this.page = nextPage
      this.error = ''
      this.isLoading = true

      try {
        const data = await getAttractions({
          city_name: target.city_name,
          adcode: target.adcode,
          keyword: this.keyword,
          page: nextPage,
          page_size: this.pageSize,
        })

        const page = normalizePage(data)
        this.items = mergeUnique(this.items, page.items)
        this.hasMore = page.hasMore
      } catch (error) {
        this.page = previousPage
        this.error = resolveErrorMessage(error, '加载更多景点失败,请稍后重试')
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 打开景点详情。
     *
     * 先放一份占位详情再请求:即使接口失败,弹窗也能正常打开并显示"暂无信息",
     * 页面不会因为详情接口异常而卡死(§40)。
     */
    async openDetail(poiId) {
      const id = poiId === null || poiId === undefined ? '' : String(poiId)
      if (!id) {
        return
      }

      this.error = ''
      this.isDetailLoading = true
      this.selectedDetail = { poi_id: id, name: '', photos: [], address: null, cost: null, tags: [] }

      try {
        const data = await getAttractionDetail(id)
        this.selectedDetail = {
          poi_id: data?.poi_id === null || data?.poi_id === undefined ? id : String(data.poi_id),
          name: typeof data?.name === 'string' ? data.name : '',
          photos: Array.isArray(data?.photos) ? data.photos : [],
          address: data?.address ?? null,
          cost: data?.cost ?? null,
          tags: normalizeTags(data?.tags),
          // 后端可能返回 location,前端直接丢弃:UI 层不持有经纬度。
        }
      } catch (error) {
        this.error = resolveErrorMessage(error, '景点详情获取失败,请稍后重试')
      } finally {
        this.isDetailLoading = false
      }
    },

    /** 关闭景点详情弹窗。 */
    closeDetail() {
      this.selectedDetail = null
    },

    /** 切换城市 / 退出登录时清空旧城市结果。 */
    resetAttractions() {
      this.items = []
      this.mode = 'default'
      this.keyword = ''
      this.page = 1
      this.pageSize = SEARCH_PAGE_SIZE
      this.hasMore = false
      this.selectedDetail = null
      this.isLoading = false
      this.isDetailLoading = false
      this.error = ''
    },
  },
})
