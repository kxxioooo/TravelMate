import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const BACKEND_ORIGIN = 'http://127.0.0.1:8000'

/**
 * 开发服务器把 /api 与 /health 代理到 FastAPI。
 *
 * 这样浏览器眼里始终只有 5173 一个源,HttpOnly Cookie 才能正常携带,
 * 前端也就可以统一请求 /api/v1/... —— v0.2 / v0.3 不需要改请求习惯。
 */
export function createViteConfig() {
  return defineConfig({
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: BACKEND_ORIGIN, changeOrigin: true },
        '/health': { target: BACKEND_ORIGIN, changeOrigin: true },
      },
    },
  })
}

export default createViteConfig()
