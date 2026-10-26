import axios from 'axios'
import { ElMessage } from 'element-plus'

import { getCurrentLocale, hasTranslation, translate } from '../i18n'

/** 所有后端接口统一前缀,与 FastAPI 的 APIRouter(prefix="/api/v1") 对齐。 */
export const API_BASE_URL = '/api/v1'

/** 状态码兜底文案的 i18n key(`error.status.*`)。 */
function statusMessageKey(status) {
  return `error.status.${status}`
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
 * 把 axios 的各种失败统一成
 * `{ status, errorCode, key, detail, message }`。
 *
 * v0.3.1 优先级(跨端契约 §5):
 *   1. `data.error_code` 有对应资源 -> `t('error.' + code)`;
 *   2. 否则用后端 `detail` 原文(向后兼容 v0.3 的中文错误);
 *   3. 否则按 HTTP 状态码兜底;
 *   4. 最后落到通用失败文案。
 *
 * `key` / `detail` / `status` 会被 store 原样保存,渲染时再按**当时**的语言
 * 解析(`formatLocalizedError`),因此切换语言后旧错误也能立即换语言。
 * `message` 是"请求失败那一刻"的快照,供 Toast 这类一次性提示直接使用。
 */
export function normalizeApiError(error) {
  if (!error?.response) {
    return {
      status: 0,
      errorCode: '',
      key: 'error.network',
      detail: '',
      message: translate('error.network'),
    }
  }

  const { status, data } = error.response
  const errorCode = typeof data?.error_code === 'string' ? data.error_code.trim() : ''
  const detail = typeof data?.detail === 'string' ? data.detail.trim() : ''
  const errorKey = errorCode ? `error.${errorCode}` : ''
  const key = errorKey && hasTranslation(errorKey) ? errorKey : ''
  const fallbackKey = statusMessageKey(status)

  let message = ''

  if (key) {
    message = translate(key)
  } else if (detail) {
    message = detail
  } else if (hasTranslation(fallbackKey)) {
    message = translate(fallbackKey)
  } else {
    message = translate('error.unknown')
  }

  return { status, errorCode, key, detail, message }
}

/** 只保留可序列化的错误字段,store 里存这个对象而不是整条 axios error。 */
export function toErrorInfo(error) {
  if (error?.normalized) {
    const { status, errorCode, key, detail } = error.normalized
    return { status, errorCode, key, detail }
  }

  const normalized = normalizeApiError(error)
  const { status, errorCode, key, detail } = normalized

  return { status, errorCode, key, detail }
}

/**
 * 统一拦截请求 / 响应:
 * - 请求:自动带上 `Accept-Language: <locale>`(契约 §1);
 * - 响应:成功直接返回;失败挂上 normalized 字段后继续抛出,
 *   网络失败 / 422 / 5xx 这类"没人管"的错误在提示层统一弹出。
 */
export function installHttpInterceptors(client) {
  client.interceptors.request.use((config) => {
    const locale = getCurrentLocale()

    if (config.headers && typeof config.headers.set === 'function') {
      config.headers.set('Accept-Language', locale)
    } else {
      config.headers = { ...(config.headers ?? {}), 'Accept-Language': locale }
    }

    return config
  })

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
