import { http } from './http'

/**
 * 按城市 adcode 获取实时天气 + 穿衣建议。
 *
 * 前端绝不直接请求高德,高德 Key 也永远不出现在前端代码里。
 */
export function getWeather(adcode) {
  const params = adcode === null || adcode === undefined || adcode === '' ? {} : { adcode: String(adcode) }
  return http.get('/weather', { params }).then((response) => response.data)
}
