import { http } from './http'

/** 去掉空参数,避免向后端发送 keyword= 这类空字符串。 */
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
 * 景点列表。
 *
 * keyword 为空 -> 默认景点模式(page_size=10);
 * keyword 非空 -> 搜索模式(page_size=20,支持 Load More)。
 */
export function getAttractions(params = {}) {
  return http.get('/attractions', { params: buildParams(params) }).then((response) => response.data)
}

/**
 * 景点详情。
 *
 * 后端可能返回 location,前端不展示坐标(§1 第 14 条)。
 */
export function getAttractionDetail(poiId) {
  return http
    .get(`/attractions/${encodeURIComponent(String(poiId ?? ''))}`)
    .then((response) => response.data)
}
