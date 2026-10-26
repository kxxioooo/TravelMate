import elementLocaleEn from 'element-plus/es/locale/lang/en'
import elementLocaleZh from 'element-plus/es/locale/lang/zh-cn'
import { createI18n } from 'vue-i18n'

import enUS from './en-US'
import zhCN from './zh-CN'

/**
 * Vue I18n 实例与语言标记的唯一入口(v0.3.1)。
 *
 * 约定:
 *   - 只有 `zh-CN` / `en-US` 两种语言,默认 `zh-CN`;
 *   - 持久化键固定为 `localStorage["travelmate.locale"]`(跨端契约 §1);
 *   - 任何模块(组件 / Pinia store / axios 拦截器)都通过这里取 i18n 与
 *     当前 locale,不在别处重复创建实例。
 */

/** 默认语言。 */
export const DEFAULT_LOCALE = 'zh-CN'

/** 允许的语言集合(跨端契约 §1)。 */
export const SUPPORTED_LOCALES = Object.freeze(['zh-CN', 'en-US'])

/** localStorage 里保存语言标记的键。 */
export const LOCALE_STORAGE_KEY = 'travelmate.locale'

/**
 * 把任意输入强制归一化成受支持的语言标记,无法识别时返回 null。
 *
 * 兼容 `zh`、`zh-Hans-CN`(浏览器 Accept-Language 风格)这类合法变体,
 * 但 `xx-YY` 这种未支持的值不会被悄悄当成中文 —— 调用方自己决定回落策略。
 */
export function coerceLocale(value) {
  const raw = String(value ?? '').trim()

  if (!raw) {
    return null
  }

  if (SUPPORTED_LOCALES.includes(raw)) {
    return raw
  }

  const lower = raw.toLowerCase()

  if (lower === 'zh' || lower.startsWith('zh-')) {
    return 'zh-CN'
  }

  if (lower === 'en' || lower.startsWith('en-')) {
    return 'en-US'
  }

  return null
}

/**
 * 把任意输入归一化成受支持的语言标记。
 *
 * 非法值一律回落到默认语言,绝不把未支持的语言写进 store。
 */
export function normalizeLocale(value) {
  return coerceLocale(value) ?? DEFAULT_LOCALE
}

/** 读取持久化的语言标记;SSR / 隐私模式下 localStorage 不可用时不抛错。 */
export function readStoredLocale() {
  try {
    return normalizeLocale(globalThis?.localStorage?.getItem(LOCALE_STORAGE_KEY))
  } catch {
    return DEFAULT_LOCALE
  }
}

/** 写入持久化的语言标记。 */
export function persistLocale(locale) {
  try {
    globalThis?.localStorage?.setItem(LOCALE_STORAGE_KEY, normalizeLocale(locale))
  } catch {
    // 存不进去只影响"刷新后保持",不能影响当前切换。
  }
}

/**
 * 按 locale 读取 Element Plus 语言包。
 *
 * Element Plus 的内置文案(分页、表格空态、表单校验)不经过 Vue I18n,
 * 必须由 App.vue 的 `<el-config-provider :locale>` 单独喂给它。
 */
export function resolveElementLocale(locale) {
  return normalizeLocale(locale) === 'en-US' ? elementLocaleEn : elementLocaleZh
}

/** 同步 `document.documentElement.lang` 与网页标题。 */
export function applyDocumentLocale(locale, title) {
  if (typeof document === 'undefined') {
    return
  }

  document.documentElement.lang = normalizeLocale(locale)

  if (title) {
    document.title = title
  }
}

/** 单例 i18n 实例;重复调用 createAppI18n() 不会重复安装。 */
let i18nInstance = null

/**
 * 创建(或复用)应用级 Vue I18n 实例。
 *
 * 初始语言直接取持久化值,保证首帧就是用户上次选择的语言,
 * 刷新时不会出现"先中文后英文"的闪烁。
 */
export function createAppI18n() {
  if (i18nInstance) {
    return i18nInstance
  }

  i18nInstance = createI18n({
    legacy: false,
    globalInjection: true,
    locale: readStoredLocale(),
    fallbackLocale: DEFAULT_LOCALE,
    messages: {
      'zh-CN': zhCN,
      'en-US': enUS,
    },
  })

  return i18nInstance
}

/** 取 i18n 实例(未创建时自动创建,方便 store / 工具函数使用)。 */
export function getAppI18n() {
  return i18nInstance ?? createAppI18n()
}

/** 当前生效的 locale(已归一化)。 */
export function getCurrentLocale() {
  return normalizeLocale(getAppI18n().global.locale.value)
}

/** 在组件外翻译文案(store / axios 拦截器 / 纯函数)。 */
export function translate(key, params) {
  if (!key) {
    return ''
  }

  return params ? getAppI18n().global.t(key, params) : getAppI18n().global.t(key)
}

/** 某个 key 是否在当前语言资源里存在。 */
export function hasTranslation(key) {
  if (!key) {
    return false
  }

  return getAppI18n().global.te(key)
}
