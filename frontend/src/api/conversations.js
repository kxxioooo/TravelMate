import { http } from './http'

/**
 * Conversation 相关接口(§15)。
 *
 * 所有接口都由后端按当前登录用户过滤(§16.1),前端不持有 user_id,
 * 也不允许任何"跨用户取会话"的调用方式。
 */

/** §15.1 当前用户全部会话,后端已按 updated_at DESC 排序。 */
export function listConversations() {
  return http.get('/conversations').then((response) => response.data)
}

/**
 * §15.2 新建会话。
 *
 * cities 允许为空数组 —— 零城市会话做通用旅行咨询(§4)。
 */
export function createConversation(cities = []) {
  return http
    .post('/conversations', { cities: Array.isArray(cities) ? cities : [] })
    .then((response) => response.data)
}

/** §15.3 会话详情;不属于当前用户时后端统一 404。 */
export function getConversation(id) {
  return http
    .get(`/conversations/${encodeURIComponent(String(id ?? ''))}`)
    .then((response) => response.data)
}

/** §15.4 整组替换当前会话的绑定城市。 */
export function updateConversationCities(id, cities = []) {
  return http
    .put(`/conversations/${encodeURIComponent(String(id ?? ''))}/cities`, {
      cities: Array.isArray(cities) ? cities : [],
    })
    .then((response) => response.data)
}
