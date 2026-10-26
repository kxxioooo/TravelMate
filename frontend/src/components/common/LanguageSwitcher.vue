<template>
  <!--
    右上角语言切换控件(v0.3.1,规格 §4.2)。

    - 两个选项始终同时可见:`中文 | English`,选中态用 is-active 突出;
    - 主站放在 Topbar 右侧(margin-left: auto),未登录页用 position="fixed"
      固定到可视区域右上角;
    - 纯按钮实现,天然可用 Tab 聚焦 + Enter / Space 触发,并带 aria-pressed。

    验收脚本依赖的 class:`.tm-language-switcher` / `.tm-lang-zh` / `.tm-lang-en`。
  -->
  <div
    class="tm-language-switcher"
    :class="{ 'is-fixed': position === 'fixed' }"
    role="group"
    :aria-label="t('app.language_switch_label')"
  >
    <button
      type="button"
      class="tm-lang-option tm-lang-zh"
      :class="{ 'is-active': isZh }"
      :aria-pressed="isZh"
      :aria-label="`${t('app.lang_zh')} (${t('app.language')})`"
      :title="t('app.lang_zh')"
      @click="handleLocaleChange(ZH_LOCALE)"
    >
      {{ t('app.lang_zh') }}
    </button>

    <span class="tm-lang-divider" aria-hidden="true">|</span>

    <button
      type="button"
      class="tm-lang-option tm-lang-en"
      :class="{ 'is-active': isEn }"
      :aria-pressed="isEn"
      :aria-label="`${t('app.lang_en')} (${t('app.language')})`"
      :title="t('app.lang_en')"
      @click="handleLocaleChange(EN_LOCALE)"
    >
      {{ t('app.lang_en') }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleStore } from '../../stores/locale'

/** 两个受支持的语言标记,与 i18n/index.js 的 SUPPORTED_LOCALES 一致。 */
const ZH_LOCALE = 'zh-CN'
const EN_LOCALE = 'en-US'

defineProps({
  /** topbar:贴在主站顶部右侧;fixed:固定在可视区域右上角(未登录页)。 */
  position: { type: String, default: 'topbar' },
})

const { t } = useI18n()
const localeStore = useLocaleStore()

const isZh = computed(() => localeStore.locale === ZH_LOCALE)
const isEn = computed(() => localeStore.locale === EN_LOCALE)

/**
 * 切换语言(唯一入口)。
 *
 * 只写 locale store —— Vue I18n、localStorage、`<html lang>`、Element Plus
 * 语言包都由 store 同步,组件不重复做这些事,也不触发任何数据请求。
 */
function handleLocaleChange(nextLocale) {
  localeStore.setLocale(nextLocale)
}
</script>
