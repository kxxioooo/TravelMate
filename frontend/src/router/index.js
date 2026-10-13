import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import OnboardingView from '../views/OnboardingView.vue'
import RegisterView from '../views/RegisterView.vue'

/** 创建应用路由:v0.1 只有四个页面。 */
export function createAppRouter() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
      { path: '/register', name: 'register', component: RegisterView, meta: { public: true } },
      { path: '/onboarding', name: 'onboarding', component: OnboardingView },
      { path: '/', name: 'home', component: HomeView },
      { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
    ],
    scrollBehavior: () => ({ top: 0 }),
  })

  installRouteGuard(router)
  return router
}

/** /login 与 /register 是匿名页面。 */
export function isPublicRoute(to) {
  return to.matched.some((record) => record.meta?.public === true)
}

/**
 * 根据 isAuthenticated 与 onboarding_completed 决定去向。
 *
 * 返回 true 表示放行,返回路由对象表示重定向。
 *   匿名访问受保护页面        -> /login
 *   已登录但未完成 onboarding -> /onboarding
 *   已完成 onboarding         -> /(并且仍然允许回 /onboarding 改偏好)
 *
 * 注意:/onboarding 同时是"首次填写"和"已登录用户修改偏好"的唯一入口
 * (Sidebar 的 Preferences 就指向它),所以完成后不能把它挡掉,
 * 否则用户再也改不了偏好。
 */
export function resolveAuthenticatedRedirect(authStore, to) {
  if (!authStore.isAuthenticated) {
    return isPublicRoute(to) ? true : { name: 'login' }
  }

  const onboardingCompleted = authStore.user?.onboarding_completed === true

  if (!onboardingCompleted) {
    return to.name === 'onboarding' ? true : { name: 'onboarding' }
  }

  // 已完成 onboarding 的人不该再看到登录/注册页
  if (to.name === 'login' || to.name === 'register') {
    return { name: 'home' }
  }

  return true
}

/** 注册全局 beforeEach:先恢复登录态,再判断去向。 */
export function installRouteGuard(router) {
  router.beforeEach(async (to) => {
    const authStore = useAuthStore()

    if (!authStore.isBootstrapped) {
      await authStore.restoreSession()
    }

    return resolveAuthenticatedRedirect(authStore, to)
  })
}
