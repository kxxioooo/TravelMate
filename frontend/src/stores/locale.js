import { defineStore } from 'pinia'

import {
  applyDocumentLocale,
  coerceLocale,
  getAppI18n,
  getCurrentLocale,
  normalizeLocale,
  persistLocale,
  readStoredLocale,
} from '../i18n'

/**
 * 语言状态中心(v0.3.1,跨端契约 §1)。
 *
 * 唯一职责:持有当前 locale,并把它同步到 Vue I18n、localStorage、
 * `document.documentElement.lang` 与网页标题。
 *
 * 这里**不做**任何数据请求 —— 切换语言只改展示语言,不重置城市、Tab、
 * 分页、Splitter 宽度、Conversation 与历史消息(规格 §4.1 / §8.2)。
 */
export const useLocaleStore = defineStore('locale', {
  state: () => ({
    locale: readStoredLocale(),
  }),

  getters: {
    isEnglish: (state) => state.locale === 'en-US',
  },

  actions: {
    /**
     * 把当前 locale 应用到所有运行时载体。
     *
     * 不校验"是否变化":启动时必须无条件刷一次,保证 i18n 与 DOM 对齐。
     */
    applyLocale(value) {
      const locale = normalizeLocale(value)

      this.locale = locale
      getAppI18n().global.locale.value = locale
      persistLocale(locale)
      applyDocumentLocale(locale, getAppI18n().global.t('app.title'))

      return locale
    },

    /**
     * 切换语言。
     *
     * 只接受 zh-CN / en-US(及其 zh、en 变体);非法值直接忽略,
     * 不把界面切到一个没有资源的语言上。
     */
    setLocale(nextLocale) {
      const coerced = coerceLocale(nextLocale)

      if (!coerced || coerced === this.locale) {
        return this.locale
      }

      return this.applyLocale(coerced)
    },

    /** 启动时初始化:读取持久化语言并同步 i18n / html lang / title。 */
    initializeLocale() {
      return this.applyLocale(this.locale)
    },
  },
})

/** 便捷函数:在 main.js 里以 pinia 实例初始化语言。 */
export function initializeLocale(pinia) {
  return useLocaleStore(pinia).initializeLocale()
}

/** 便捷函数:供非组件代码(拦截器 / store)切换语言。 */
export function setLocale(nextLocale, pinia) {
  return useLocaleStore(pinia).setLocale(nextLocale)
}

/** 当前生效的 locale 标记(直接从 i18n 读取,保证与渲染期一致)。 */
export function currentLocale() {
  return getCurrentLocale()
}
