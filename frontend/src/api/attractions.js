import { getCurrentLocale } from '../i18n'
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
 *
 * 语言:统一由 axios 拦截器带上 `Accept-Language`,这里再显式补一个 `locale`
 * 参数作为冗余声明(后端以 Accept-Language 为主)。响应同时包含 `name` 与
 * `name_en` 等双语字段,因此**切换语言不需要重新请求**,只重新格式化。
 *
 * 英文关键词(`ancient town`)由后端解析成经验证的中文关键词再查高德,
 * 前端不负责翻译,也绝不把英文直接丢给高德。
 */
export function getAttractions(params = {}) {
  return http
    .get('/attractions', {
      params: { ...buildParams(params), locale: getCurrentLocale() },
    })
    .then((response) => response.data)
}

/**
 * 景点详情。
 *
 * 后端可能返回 location,前端不展示坐标;`poi_id` 不随语言变化。
 */
export function getAttractionDetail(poiId) {
  return http
    .get(`/attractions/${encodeURIComponent(String(poiId ?? ''))}`, {
      params: { locale: getCurrentLocale() },
    })
    .then((response) => response.data)
}
