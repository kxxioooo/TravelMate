import { getCurrentLocale } from '../i18n'
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
 * 后端 = 受限 DeepSeek 生成美食名称(中英双语) + 高德真实餐厅 POI,
 * 每种美食最多 2 家代表餐厅;查餐厅时用的仍是中文菜名。
 *
 * 语言:统一由 axios 拦截器带 `Accept-Language`,这里再冗余声明 `locale`。
 * 响应同时带 `name` / `name_en` / `description_en`,切换语言只需重新格式化。
 *
 * 注意:这一路要调用一次 DeepSeek + 对每种美食查一次高德(受 QPS 限流影响),
 * 实测耗时可达 20 秒以上,远超 http.js 默认的 15 秒。必须单独放宽超时,
 * 否则请求会被前端自己掐断,页面表现为"美食加载不出来"而后端日志里根本没有请求。
 */
export function getFeaturedFoods(city) {
  return http
    .get('/food/featured', {
      params: buildParams({
        city_name: city?.city_name ?? '',
        adcode: city?.adcode ?? '',
        locale: getCurrentLocale(),
      }),
      timeout: 90000,
    })
    .then((response) => response.data)
}

/**
 * 关键词搜索当前城市的餐厅(例如 `火锅` / `hot pot`)。
 *
 * 英文关键词同样由后端转成经验证的中文查询词,前端只负责把用户原文传上去。
 */
export function searchFoodRestaurants(params = {}) {
  return http
    .get('/food/restaurants', {
      params: { ...buildParams(params), locale: getCurrentLocale() },
    })
    .then((response) => response.data)
}

/** 餐厅详情:人均 / 地址 / 评分 / 预订电话。 */
export function getRestaurantDetail(poiId) {
  return http
    .get(`/food/restaurants/${encodeURIComponent(String(poiId ?? ''))}`, {
      params: { locale: getCurrentLocale() },
    })
    .then((response) => response.data)
}
