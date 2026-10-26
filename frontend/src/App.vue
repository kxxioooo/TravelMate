<template>
  <!--
    全局语言容器(v0.3.1)。

    Element Plus 的内置文案(分页、空态、表单校验等)不走 Vue I18n,
    必须通过 `<el-config-provider :locale>` 同步切换;业务语言由
    Vue I18n + locale store 负责。这里只做配置,不放任何业务逻辑。
  -->
  <el-config-provider :locale="elementLocale">
    <router-view />
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'

import { resolveElementLocale } from './i18n'
import { useLocaleStore } from './stores/locale'

const localeStore = useLocaleStore()

/** `zh-CN` -> Element Plus 中文包,`en-US` -> 英文包。 */
const elementLocale = computed(() => resolveElementLocale(localeStore.locale))
</script>
