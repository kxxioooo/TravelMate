import * as ElementPlusIcons from '@element-plus/icons-vue'
import ElementPlus from 'element-plus'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import 'element-plus/dist/index.css'
import './styles/global.css'

import App from './App.vue'
import { createAppI18n } from './i18n'
import { createAppRouter } from './router'
import { initializeLocale } from './stores/locale'

/**
 * 应用启动器:装配 Pinia / Vue I18n / Router / Element Plus 后挂载。
 *
 * 顺序很重要:
 *   1. Pinia 必须先于 Router 安装,路由守卫里才能拿到 auth store;
 *   2. Vue I18n 与 Pinia 就绪后立刻初始化 locale,保证首帧语言正确
 *      (读 localStorage -> 同步 i18n、`<html lang>`、网页标题);
 *   3. Element Plus 的内置文案由 App.vue 的 `<el-config-provider :locale>`
 *      单独喂语言包,这里不重复安装。
 */
export function bootstrapApp() {
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.use(createAppI18n())
  initializeLocale(pinia)

  app.use(createAppRouter())
  app.use(ElementPlus)

  for (const [name, component] of Object.entries(ElementPlusIcons)) {
    app.component(name, component)
  }

  return app.mount('#app')
}

bootstrapApp()
