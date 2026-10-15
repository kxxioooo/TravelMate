/**
 * 展示层兜底工具(v0.2 新增)。
 *
 * v0.2 的景点 / 美食 / 餐厅数据全部来自第三方 API,任何字段都可能为
 * null、undefined、空字符串或空数组。这里统一把"没有数据"翻译成
 * "暂无信息",保证:
 *   1. 页面在 API 异常时不会崩(§40 验收标准);
 *   2. 界面上永远不会出现 undefined / [object Object] 这类脏文本;
 *   3. 绝不替 API 编造价格、评分、地址、电话(§36 缺失数据规则)。
 */

/** 缺失数据的统一文案。 */
export const UNKNOWN_TEXT = '暂无信息'

/**
 * 把任意 API 值转成可安全渲染的文本。
 *
 * null / undefined / "" / [] 统一输出 "暂无信息"。
 */
export function displayOrUnknown(value) {
  if (Array.isArray(value)) {
    const parts = value.map((item) => displayOrUnknown(item)).filter((text) => text !== UNKNOWN_TEXT)
    return parts.length ? parts.join('、') : UNKNOWN_TEXT
  }

  if (value === null || value === undefined) {
    return UNKNOWN_TEXT
  }

  if (typeof value === 'string') {
    const text = value.trim()
    return text || UNKNOWN_TEXT
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : UNKNOWN_TEXT
  }

  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }

  // 对象没有可以直接展示的语义,一律当成缺失,避免渲染 [object Object]。
  return UNKNOWN_TEXT
}

/**
 * 价格 / 门票 / 人均。
 *
 * - 数字或纯数字字符串 -> "¥xx"
 * - 非空文本(例如高德返回的"免费")-> 原文照显,符合"API 有值就显示"
 * - 其余 -> "暂无信息"
 *
 * 刻意不做任何货币换算或猜测。
 */
export function formatPrice(value) {
  if (value === null || value === undefined || Array.isArray(value)) {
    return UNKNOWN_TEXT
  }

  if (typeof value === 'boolean') {
    return UNKNOWN_TEXT
  }

  const text = String(value).trim()
  if (!text) {
    return UNKNOWN_TEXT
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
