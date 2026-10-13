import axios from 'axios'
import { ElMessage } from 'element-plus'

/** 所有后端接口统一前缀,与 FastAPI 的 APIRouter(prefix="/api/v1") 对齐。 */
export const API_BASE_URL = '/api/v1'

const STATUS_MESSAGES = {
  400: '请求参数有误',
  401: '未登录或登录已失效',
  403: '没有权限执行该操作',
  404: '请求的资源不存在',
  409: '数据冲突,请检查后重试',
  422: '提交的数据格式不正确',
  500: '服务器暂时不可用',
}

/** 创建 Axios 实例:带 Cookie、统一前缀、统一超时。 */
export function createHttpClient() {
  return axios.create({
    baseURL: API_BASE_URL,
    timeout: 15000,
    withCredentials: true,
    headers: { 'Content-Type': 'application/json' },
  })
}

/**
 * 把 axios 的各种失败统一成 { status, message }。
 *
 * message 优先使用后端返回的 detail(已经是人话),否则按状态码兜底,
 * 保证界面上永远不会出现 Traceback / SQLAlchemyError。
 */
export function normalizeApiError(error) {
  if (!error?.response) {
    return { status: 0, message: '网络连接失败,请确认后端服务已启动' }
  }

  const { status, data } = error.response
  const detail = typeof data?.detail === 'string' ? data.detail : null

  return { status, message: detail || STATUS_MESSAGES[status] || '请求失败,请稍后重试' }
}

/**
 * 统一拦截响应:
 * - 成功直接返回 response;
 * - 失败挂上 normalized 字段后继续抛出,调用方只读 normalized.message;
 * - 网络失败 / 422 / 5xx 这类"没人管"的错误在提示层统一弹出。
 */
export function installHttpInterceptors(client) {
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      const normalized = normalizeApiError(error)

      if (normalized.status === 0 || normalized.status === 422 || normalized.status >= 500) {
        ElMessage.error(normalized.message)
      }

      error.normalized = normalized
      return Promise.reject(error)
    },
  )

  return client
}

export const http = installHttpInterceptors(createHttpClient())
