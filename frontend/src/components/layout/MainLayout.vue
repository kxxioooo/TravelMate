<template>
  <div class="tm-shell">
    <AppSidebar
      :collapsed="sidebarCollapsed"
      @collapse="handleSidebarCollapse"
      @open-preferences="emit('open-preferences')"
      @open-prompts="emit('open-prompts')"
      @open-settings="emit('open-settings')"
    />

    <div
      class="tm-shell-main"
      :style="{
        marginLeft: sidebarCollapsed
          ? 'var(--tm-sidebar-collapsed-width)'
          : 'var(--tm-sidebar-width)',
      }"
    >
      <header class="tm-topbar">
        <TopCitySearch :selected-city="selectedCity" @city-selected="handleCitySelected" />
        <!-- 语言切换固定在 Topbar 最右侧(规格 §4.2:只放顶部,不进 Sidebar / AI Drawer) -->
        <LanguageSwitcher />
      </header>

      <main class="tm-content" :class="{ 'tm-content--workspace': Boolean(selectedCity) }">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

import AppSidebar from './AppSidebar.vue'
import TopCitySearch from './TopCitySearch.vue'
import LanguageSwitcher from '../common/LanguageSwitcher.vue'

defineProps({
  selectedCity: { type: Object, default: null },
})

const emit = defineEmits(['city-selected', 'open-preferences', 'open-prompts', 'open-settings'])

const sidebarCollapsed = ref(false)

/**
 * 同步主内容区可用宽度:折叠后让出 236px -> 72px。
 *
 * 当已经选中城市时,主内容区切换成"可拖动双栏"布局:
 * CityWorkspace 需要在固定高度里自行滚动,所以这里不再让整页滚动。
 */
function handleSidebarCollapse(collapsed) {
  sidebarCollapsed.value = Boolean(collapsed)
}

/** 把 TopCitySearch 的事件继续向 HomeView 传递。 */
function handleCitySelected(city) {
  emit('city-selected', city)
}
</script>

<style scoped>
.tm-topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  gap: 16px;
  align-items: center;
  height: var(--tm-topbar-height);
  padding: 0 32px;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid var(--tm-border);
  backdrop-filter: blur(8px);
}

@media (max-width: 900px) {
  .tm-topbar {
    gap: 10px;
    padding: 0 16px;
  }
}
</style>
