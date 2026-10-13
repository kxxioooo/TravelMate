import { http } from './http'

/** 读取当前用户偏好;从未保存过会得到一份空结构而不是 404。 */
export function getMyPreferences() {
  return http.get('/preferences/me').then((response) => response.data)
}

/** 保存 / 修改偏好,后端同时会把 onboarding_completed 置为 true。 */
export function saveMyPreferences(payload) {
  return http.put('/preferences/me', payload).then((response) => response.data)
}

/** Skip:只标记 Onboarding 完成,不写入偏好。 */
export function skipOnboarding() {
  return http.post('/preferences/skip').then((response) => response.data)
}
