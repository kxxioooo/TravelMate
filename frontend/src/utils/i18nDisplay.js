import { getCurrentLocale, translate } from '../i18n'
import { enrichCity } from './localeSearch'

/**
 * 双语实体安全展示(v0.3.1,跨端契约 §2)。
 *
 * 规则(英文模式):
 *   - 有英文名:`English (中文)`;
 *   - 只有中文名:只显示中文 —— **绝不伪造**英文名;
 *   - 两者都没有:交给 `formatLocalizedUnknown()` 输出当前语言的"暂无信息"。
 *
 * 这些函数只作用于**展示**,返回值永远不会被写回请求参数:
 * 发给后端的城市标识永远是 `city_name`(中文)+ `adcode`。
 */

/** 任意值 -> 去空白的字符串(非字符串 / 空值统一成 '')。 */
function toText(value) {
  if (typeof value === 'string') {
    return value.trim()
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value)
  }

  return ''
}

/** 当前语言下"暂无信息"的文案。 */
function unknownText(t) {
  return typeof t === 'function' ? t('common.unknown') : translate('common.unknown')
}

/**
 * 名称双语展示。
 *
 * zh-CN -> 中文名(缺失时退回英文);en-US -> `English (中文)`,只有中文就只显示中文。
 */
export function displayBilingualName(nameZh, nameEn, locale) {
  const zh = toText(nameZh)
  const en = toText(nameEn)
  const target = locale ?? getCurrentLocale()

  if (target === 'en-US') {
    if (en && zh) {
      return `${en} (${zh})`
    }

    return en || zh
  }

  return zh || en
}

/**
 * 地址双语展示。
 *
 * 与名称同一规则,但语义上强调"英文地址 + 括号中文原文",
 * 便于用户在地图 / 导航里对照真实中文地址。
 */
export function displayBilingualAddress(addressZh, addressEn, locale) {
  const zh = toText(addressZh)
  const en = toText(addressEn)
  const target = locale ?? getCurrentLocale()

  if (target === 'en-US') {
    if (en && zh) {
      return `${en} (${zh})`
    }

    return en || zh
  }

  return zh || en
}

/**
 * 把实体(景点 / 美食 / 餐厅)一次格式化成可直接渲染的展示字段。
 *
 * 只读白名单字段,返回新对象;调用方拿到的 `_en` 字段仅用于展示,
 * 不要写回 store 或请求参数。
 */
export function formatLocalizedEntity(entity, locale, options = {}) {
  const source = entity && typeof entity === 'object' ? entity : {}
  const target = locale ?? getCurrentLocale()

  const nameZhKey = options.nameZhKey ?? 'name'
  const nameEnKey = options.nameEnKey ?? 'name_en'
  const addressZhKey = options.addressZhKey ?? 'address'
  const addressEnKey = options.addressEnKey ?? 'address_en'
  const descriptionZhKey = options.descriptionZhKey ?? 'description'
  const descriptionEnKey = options.descriptionEnKey ?? 'description_en'

  const nameZh = toText(source[nameZhKey])
  const nameEn = toText(source[nameEnKey])
  const addressZh = toText(source[addressZhKey])
  const addressEn = toText(source[addressEnKey])
  const descriptionZh = toText(source[descriptionZhKey])
  const descriptionEn = toText(source[descriptionEnKey])

  return {
    nameZh,
    nameEn,
    name: displayBilingualName(nameZh, nameEn, target),
    addressZh,
    addressEn,
    address: displayBilingualAddress(addressZh, addressEn, target),
    // 英文模式优先用后端给的英文描述;没有就退回原文(降级,不伪造)
    description: target === 'en-US' ? descriptionEn || descriptionZh : descriptionZh || descriptionEn,
  }
}

/**
 * 本地化的"缺失数据"展示。
 *
 * null / undefined / "" / [] / 普通对象统一输出当前语言的 `common.unknown`,
 * 数组按语言习惯拼接(中文用顿号,英文用逗号)。
 */
export function formatLocalizedUnknown(value, t, locale) {
  const target = locale ?? getCurrentLocale()
  const fallback = unknownText(t)
  const separator = target === 'en-US' ? ', ' : '、'

  if (Array.isArray(value)) {
    const parts = value
      .map((item) => formatLocalizedUnknown(item, t, target))
      .filter((text) => text && text !== fallback)

    return parts.length ? parts.join(separator) : fallback
  }

  if (value === null || value === undefined) {
    return fallback
  }

  if (typeof value === 'string') {
    return value.trim() || fallback
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : fallback
  }

  if (typeof value === 'boolean') {
    const key = value ? 'common.yes' : 'common.no'
    return typeof t === 'function' ? t(key) : translate(key)
  }

  // 对象没有可以直接展示的语义,一律当成缺失,避免渲染 [object Object]。
  return fallback
}

/**
 * 城市名双语展示:`Chengdu (成都)` / `成都`。
 *
 * 后端与历史记录只给中文名 + adcode,英文名从静态城市索引补齐;
 * 索引里也没有英文名时只显示中文,不臆造译名。
 */
export function displayCityName(city, locale) {
  const target = locale ?? getCurrentLocale()
  if (!city) {
    return ''
  }

  const record = enrichCity(city) ?? {}
  const display = displayBilingualName(record.city_name, record.city_name_en, target)

  return display || toText(city.city_name)
}

/** 省份名双语展示:`Sichuan (四川)` / `四川`。 */
export function displayProvinceName(city, locale) {
  const target = locale ?? getCurrentLocale()
  if (!city) {
    return ''
  }

  const record = enrichCity(city) ?? {}
  const display = displayBilingualName(record.province, record.province_en, target)

  return display || toText(city.province)
}

/** 城市 + 省份的完整展示(`Chengdu (成都) · Sichuan (四川)`),空的部分自动省略。 */
export function displayCityLabel(city, locale) {
  const parts = [displayCityName(city, locale), displayProvinceName(city, locale)].filter(Boolean)

  return parts.join(' · ')
}

/**
 * 本地化错误文案(跨端契约 §5)。
 *
 * 优先级:已映射的 `error.<error_code>` > 后端 `detail` 原文 > 状态码兜底文案
 * > 调用方的场景兜底 key > 通用失败文案。
 *
 * `error` 既支持 store 里保存的对象 `{ key, detail, status }`,也兼容旧字符串。
 * 第二个参数可以是组件里的 `t`,也可以是 `{ t, locale, fallbackKey }`。
 */
export function formatLocalizedError(error, options = {}) {
  if (!error) {
    return ''
  }

  const normalizedOptions = typeof options === 'function' ? { t: options } : options ?? {}
  const t = normalizedOptions.t
  const fallbackKey = normalizedOptions.fallbackKey ?? ''
  const translateWith = (key) => (typeof t === 'function' ? t(key) : translate(key))

  if (typeof error === 'string') {
    return error.trim()
  }

  const key = typeof error.key === 'string' ? error.key : ''

  if (key) {
    const text = translateWith(key)
    if (text && text !== key) {
      return text
    }
  }

  if (typeof error.detail === 'string' && error.detail.trim()) {
    return error.detail.trim()
  }

  if (error.status !== null && error.status !== undefined && error.status !== '') {
    const statusKey = `error.status.${error.status}`
    const text = translateWith(statusKey)
    if (text && text !== statusKey) {
      return text
    }
  }

  if (fallbackKey) {
    const text = translateWith(fallbackKey)
    if (text && text !== fallbackKey) {
      return text
    }
  }

  return translateWith('error.unknown')
}
