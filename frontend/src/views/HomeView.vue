<template>
  <MainLayout
    :selected-city="selectedCity"
    @city-selected="handleCitySelected"
    @open-preferences="handleOpenPreferences"
    @open-prompts="handleOpenPrompts"
    @open-settings="handleOpenSettings"
  >
    <section class="tm-hero">
      <h1 class="tm-hero-title">你好,{{ authStore.user?.username ?? '旅行者' }}</h1>

      <p v-if="selectedCity" class="tm-hero-sub">
        已选择:<strong>{{ selectedCity.city_name }} · {{ selectedCity.province }}</strong>
        <span class="tm-muted">(城市详细信息将在 v0.2 提供)</span>
      </p>
      <p v-else class="tm-hero-sub tm-muted">在顶部搜索并选择一个城市,开始规划你的旅程。</p>
    </section>

    <AiPlaceholder ref="aiPlaceholderRef" />
  </MainLayout>

  <!-- Drawer / Dialog:同一时刻只开一个,由 activePanel 决定 -->
  <el-dialog
    :model-value="activePanel !== null"
    :title="activePanel === 'prompts' ? 'Recommended Prompts' : 'Settings'"
    width="620px"
    align-center
    @update:model-value="closeActivePanel"
  >
    <RecommendedPromptsPanel
      v-if="activePanel === 'prompts'"
      @prompt-selected="handlePromptSelected"
      @close="closeActivePanel"
    />
    <SettingsPanel v-else-if="activePanel === 'settings'" @close="closeActivePanel" />
  </el-dialog>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import AiPlaceholder from '../components/home/AiPlaceholder.vue'
import RecommendedPromptsPanel from '../components/home/RecommendedPromptsPanel.vue'
import SettingsPanel from '../components/home/SettingsPanel.vue'
import MainLayout from '../components/layout/MainLayout.vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const selectedCity = ref(null)
const activePanel = ref(null)
const aiPlaceholderRef = ref(null)

/** 记录当前城市。v0.1 不请求高德,只保留完整的 city 对象。 */
function handleCitySelected(city) {
  selectedCity.value = city
  if (city) {
    ElMessage.success(`已选择 ${city.city_name}`)
  }
}

/**
 * 偏好只有一处编辑入口:直接进 Onboarding 页面,
 * 它既能首次填写也能回显修改,避免两套偏好表单走偏。
 */
function handleOpenPreferences() {
  router.push({ name: 'onboarding' })
}

/** 打开推荐问题面板。 */
function handleOpenPrompts() {
  activePanel.value = 'prompts'
}

/** 打开设置面板。 */
function handleOpenSettings() {
  activePanel.value = 'settings'
}

/** 把静态 Prompt 传给 AI Placeholder。v0.1 只填入,不发送。 */
function handlePromptSelected(prompt) {
  aiPlaceholderRef.value?.setDraftPrompt(prompt)
  closeActivePanel()
}

/** 关闭当前 Drawer / Dialog。 */
function closeActivePanel() {
  activePanel.value = null
}
</script>

<style scoped>
.tm-hero {
  margin-bottom: 24px;
}

.tm-hero-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 700;
  color: var(--tm-primary-dark);
}

.tm-hero-sub {
  margin: 0;
  font-size: 14px;
  color: var(--tm-ink);
}
</style>
