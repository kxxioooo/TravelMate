import * as ElementPlusIcons from '@element-plus/icons-vue'
import ElementPlus from 'element-plus'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import 'element-plus/dist/index.css'
import './styles/global.css'

import App from './App.vue'
import { createAppRouter } from './router'

/**
 * 应用启动器:装配 Pinia / Router / Element Plus 后挂载。
 *
 * 顺序很重要 —— Pinia 必须先于 Router 安装,路由守卫里才能拿到 auth store。
 */
export function bootstrapApp() {
  const app = createApp(App)

  app.use(createPinia())
  app.use(createAppRouter())
  app.use(ElementPlus)

  for (const [name, component] of Object.entries(ElementPlusIcons)) {
    app.component(name, component)
  }

  return app.mount('#app')
}

bootstrapApp()
