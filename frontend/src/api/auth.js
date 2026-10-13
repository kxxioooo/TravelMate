import { http } from './http'

/** 注册:成功后后端会直接写下 HttpOnly Cookie。 */
export function register(payload) {
  return http.post('/auth/register', payload).then((response) => response.data)
}

/** 登录。 */
export function login(payload) {
  return http.post('/auth/login', payload).then((response) => response.data)
}

/** 退出:清 Cookie。 */
export function logout() {
  return http.post('/auth/logout').then((response) => response.data)
}

/** 当前用户:刷新页面后用它恢复登录态。 */
export function getCurrentUser() {
  return http.get('/auth/me').then((response) => response.data)
}
