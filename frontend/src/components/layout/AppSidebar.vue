<template>
  <aside class="tm-sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="tm-sidebar-brand">
      <span class="tm-sidebar-logo">TM</span>
      <span v-show="!collapsed" class="tm-sidebar-name">TravelMate</span>
    </div>

    <!-- Sidebar 里永远不放 City Search,也不放语言切换(语言切换固定在 Topbar 右侧) -->
    <nav class="tm-sidebar-nav" :aria-label="t('nav.aria_label')">
      <button type="button" class="tm-nav-item" @click="openPreferences">
        <el-icon><Star /></el-icon>
        <span v-show="!collapsed">{{ t('nav.preferences') }}</span>
      </button>

      <button type="button" class="tm-nav-item" @click="openRecommendedPrompts">
        <el-icon><MagicStick /></el-icon>
        <span v-show="!collapsed">{{ t('nav.recommended_prompts') }}</span>
      </button>

      <button type="button" class="tm-nav-item" @click="openSettings">
        <el-icon><Setting /></el-icon>
        <span v-show="!collapsed">{{ t('nav.settings') }}</span>
      </button>
    </nav>

    <div class="tm-sidebar-spacer" />

    <div class="tm-sidebar-user">
      <el-avatar :size="30" class="tm-sidebar-avatar">
        {{ (authStore.user?.username ?? 'U').charAt(0).toUpperCase() }}
      </el-avatar>
      <div v-show="!collapsed" class="tm-sidebar-user-meta">
        <span class="tm-sidebar-username">{{ authStore.user?.username }}</span>
        <button type="button" class="tm-sidebar-logout" @click="handleLogout">
          {{ t('nav.logout') }}
        </button>
      </div>
    </div>

    <button
      type="button"
      class="tm-sidebar-collapse"
      :aria-label="collapsed ? t('nav.expand') : t('nav.collapse')"
      @click="toggleCollapse"
    >
      <el-icon v-if="collapsed"><DArrowRight /></el-icon>
      <el-icon v-else><DArrowLeft /></el-icon>
      <span v-show="!collapsed">{{ t('nav.collapse') }}</span>
    </button>
  </aside>
</template>

<script setup>
import { DArrowLeft, DArrowRight, MagicStick, Setting, Star } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../../stores/auth'
import { usePreferencesStore } from '../../stores/preferences'

const { t } = useI18n()

const props = defineProps({
  collapsed: { type: Boolean, default: false },
})

const emit = defineEmits(['collapse', 'open-preferences', 'open-prompts', 'open-settings'])

const router = useRouter()
const authStore = useAuthStore()
const preferencesStore = usePreferencesStore()

/** 展开 / 收起 Sidebar,把意图交给 MainLayout 统一持有状态。 */
function toggleCollapse() {
  emit('collapse', !props.collapsed)
}

/** 打开偏好面板。 */
function openPreferences() {
  emit('open-preferences')
}

/** 打开推荐问题面板。 */
function openRecommendedPrompts() {
  emit('open-prompts')
}

/** 打开设置面板。 */
function openSettings() {
  emit('open-settings')
}

/** 退出登录:清本地状态 + 清偏好 + 回登录页。 */
async function handleLogout() {
  await authStore.logoutUser()
  preferencesStore.resetPreferences()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.tm-sidebar {
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  width: var(--tm-sidebar-width);
  padding: 18px 14px 14px;
  color: var(--tm-sidebar-ink);
  background: var(--tm-sidebar-bg);
  transition: width 0.2s ease;
}

.tm-sidebar.is-collapsed {
  width: var(--tm-sidebar-collapsed-width);
  padding-right: 10px;
  padding-left: 10px;
}

.tm-sidebar-brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 4px 6px 20px;
}

.tm-sidebar-logo {
  display: grid;
  flex: none;
  place-items: center;
  width: 32px;
  height: 32px;
  font-size: 13px;
  font-weight: 700;
  color: #10302d;
  background: var(--tm-accent);
  border-radius: 9px;
}

.tm-sidebar-name {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
}

.tm-sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tm-nav-item,
.tm-sidebar-collapse,
.tm-sidebar-logout {
  font: inherit;
  cursor: pointer;
  background: none;
  border: 0;
}

.tm-nav-item {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  font-size: 14px;
  color: var(--tm-sidebar-ink);
  white-space: nowrap;
  border-radius: 9px;
  transition: background 0.15s ease, color 0.15s ease;
}

.tm-nav-item:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.09);
}

.tm-sidebar-spacer {
  flex: 1;
}

.tm-sidebar-user {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.tm-sidebar-avatar {
  flex: none;
  font-size: 13px;
  color: #10302d;
  background: #9fd0c9;
}

.tm-sidebar-user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.tm-sidebar-username {
  overflow: hidden;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tm-sidebar-logout {
  padding: 0;
  font-size: 12px;
  color: #8fb6b1;
  text-align: left;
}

.tm-sidebar-logout:hover {
  color: #fff;
}

.tm-sidebar-collapse {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  padding: 9px;
  font-size: 12px;
  color: #8fb6b1;
  border-radius: 9px;
}

.tm-sidebar-collapse:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.09);
}
</style>
