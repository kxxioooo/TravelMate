import { http } from './http'

/**
 * 当前登录用户的最近浏览城市。
 *
 * 后端按 (user_id, adcode) 去重并按 viewed_at 倒序,建议最多返回 10 个,
 * 因此前端直接原样使用,不再排序。
 */
export function getRecentCities() {
  return http.get('/cities/history').then((response) => response.data)
}

/**
 * 记录一次城市浏览。
 *
 * 只在用户"真正选中城市"后调用(由 cityStore.openCity 统一发起),
 * 用户仅在输入框里打字时绝不写历史。
 */
export function recordCityView(city) {
  return http
    .post('/cities/history', {
      city_name: city?.city_name ?? '',
      province: city?.province ?? null,
      adcode: city?.adcode === null || city?.adcode === undefined ? '' : String(city.adcode),
    })
    .then((response) => response.data)
}
