import { formatLocalizedUnknown } from './i18nDisplay'

/**
 * 展示层兜底工具。
 *
 * v0.2 的景点 / 美食 / 餐厅数据全部来自第三方 API,任何字段都可能为
 * null、undefined、空字符串或空数组。这里统一把"没有数据"翻译成当前语言的
 * "暂无信息",保证:
 *   1. 页面在 API 异常时不会崩;
 *   2. 界面上永远不会出现 undefined / [object Object] 这类脏文本;
 *   3. 绝不替 API 编造价格、评分、地址、电话。
 *
 * v0.3.1:缺失文案不再硬编码,统一委托 `utils/i18nDisplay.js` 的
 * `formatLocalizedUnknown()`(跟随当前 locale,无需调用方传参)。
 */

/** 缺失数据的统一文案(当前语言)。 */
export function unknownText() {
  return formatLocalizedUnknown(null)
}

/**
 * 把任意 API 值转成可安全渲染的文本。
 *
 * null / undefined / "" / [] 统一输出当前语言的 "暂无信息",
 * 数组按语言习惯拼接(中文顿号 / 英文逗号)。
 */
export function displayOrUnknown(value) {
  return formatLocalizedUnknown(value)
}

/**
 * 价格 / 门票 / 人均。
 *
 * - 数字或纯数字字符串 -> "¥xx"
 * - 非空文本(例如高德返回的"免费")-> 原文照显,符合"API 有值就显示"
 * - 其余 -> 当前语言的 "暂无信息"
 *
 * 刻意不做任何货币换算或猜测。
 */
export function formatPrice(value) {
  if (value === null || value === undefined || Array.isArray(value)) {
    return displayOrUnknown(null)
  }

  if (typeof value === 'boolean') {
    return displayOrUnknown(null)
  }

  const text = String(value).trim()
  if (!text) {
    return displayOrUnknown(null)
  }

  const numeric = Number(text)
  if (Number.isFinite(numeric)) {
    return `¥${numeric}`
  }

  return text
}

/** 只接受 http(s) 绝对地址、协议相对地址和站点内相对地址。 */
function isUsablePhotoUrl(value) {
  if (typeof value !== 'string') {
    return false
  }

  const url = value.trim()
  if (!url) {
    return false
  }

  return /^https?:\/\//i.test(url) || /^\/\//.test(url) || /^\/(?!\/)/.test(url)
}

/**
 * 过滤掉空 URL、重复 URL 和非法字符串,返回可直接交给 `el-image` 的数组。
 *
 * 兼容两种输入:
 *   - 详情接口的 `photos: [{ url, title }]`
 *   - 列表接口的 `cover_photo: "https://..."`
 */
export function safePhotoUrls(photos) {
  const source = Array.isArray(photos) ? photos : [photos]
  const seen = new Set()
  const urls = []

  for (const item of source) {
    const candidate = typeof item === 'string' ? item : item?.url
    if (!isUsablePhotoUrl(candidate)) {
      continue
    }

    const url = candidate.trim()
    if (seen.has(url)) {
      continue
    }

    seen.add(url)
    urls.push(url)
  }

  return urls
}
