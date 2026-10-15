import { http } from './http'

/** 去掉空参数,避免把 keyword= / page= 之类空值发给后端。 */
function buildParams(params) {
  const result = {}

  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === null || value === undefined || value === '') {
      continue
    }
    result[key] = value
  }

  return result
}

/**
 * 当前城市的 10 种代表性当地美食。
 *
 * 后端 = 受限 DeepSeek 生成美食名称 + 高德真实餐厅 POI,
 * 每种美食最多 2 家代表餐厅。
 */
export function getFeaturedFoods(city) {
  return http
    .get('/food/featured', {
      params: buildParams({
        city_name: city?.city_name ?? '',
        adcode: city?.adcode ?? '',
      }),
    })
    .then((response) => response.data)
}

/** 关键词搜索当前城市的餐厅(例如"火锅"),分页结果。 */
export function searchFoodRestaurants(params = {}) {
  return http.get('/food/restaurants', { params: buildParams(params) }).then((response) => response.data)
}

/** 餐厅详情:人均 / 地址 / 评分 / 预订电话。 */
export function getRestaurantDetail(poiId) {
  return http
    .get(`/food/restaurants/${encodeURIComponent(String(poiId ?? ''))}`)
    .then((response) => response.data)
}
