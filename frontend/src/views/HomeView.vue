<template>
  <MainLayout
    :selected-city="cityStore.selectedCity"
    @city-selected="handleCitySelected"
    @open-preferences="handleOpenPreferences"
    @open-prompts="handleOpenPrompts"
    @open-settings="handleOpenSettings"
  >
    <CityWorkspace
      :city="cityStore.selectedCity"
      :weather="cityStore.weather"
      :clothing-advice="cityStore.clothingAdvice"
      :weather-loading="cityStore.isWeatherLoading"
      :username="authStore.user?.username ?? ''"
    >
      <template #ai>
        <AiPlaceholder ref="aiPlaceholderRef" />
      </template>
    </CityWorkspace>
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
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AiPlaceholder from '../components/home/AiPlaceholder.vue'
import RecommendedPromptsPanel from '../components/home/RecommendedPromptsPanel.vue'
import SettingsPanel from '../components/home/SettingsPanel.vue'
import CityWorkspace from '../components/city/CityWorkspace.vue'
import MainLayout from '../components/layout/MainLayout.vue'
import { useAttractionStore } from '../stores/attractions'
import { useAuthStore } from '../stores/auth'
import { useCityStore } from '../stores/city'
import { useFoodStore } from '../stores/food'

const router = useRouter()
const authStore = useAuthStore()
const cityStore = useCityStore()
const attractionStore = useAttractionStore()
const foodStore = useFoodStore()

const activePanel = ref(null)
const aiPlaceholderRef = ref(null)

/**
 * 选中城市后的统一入口。
 *
 * - 城市上下文(浏览历史 + 天气)全部由 cityStore.openCity 负责;
 * - 天气与默认 10 个景点并行获取(§3 用户流程);
 * - 这里刻意不加载十大美食:默认 Tab 是景点,美食等用户第一次
 *   切到"美食" Tab 再加载。
 */
async function handleCitySelected(city) {
  if (!city?.city_name) {
    return
  }

  const cityTask = cityStore.openCity(city)
  const attractionTask = attractionStore.loadDefaultAttractions(city)
  foodStore.resetFoodState()

  await Promise.all([cityTask, attractionTask])
  ElMessage.success(`已选择 ${city.city_name}`)
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

/** 把静态 Prompt 传给 AI Placeholder。v0.2 仍然只填入,不发送。 */
function handlePromptSelected(prompt) {
  aiPlaceholderRef.value?.setDraftPrompt(prompt)
  closeActivePanel()
}

/** 关闭当前 Drawer / Dialog。 */
function closeActivePanel() {
  activePanel.value = null
}

/**
 * 退出登录时清空城市上下文。
 *
 * AppSidebar 只负责清 auth / preferences,城市相关状态在这里跟随
 * 登录态一起清掉,避免下一个账号看到上一个账号的城市数据。
 * 用 sync flush:退出后路由会立刻跳转,不能等下一次渲染。
 */
watch(
  () => authStore.isAuthenticated,
  (isAuthenticated) => {
    if (isAuthenticated) {
      return
    }

    cityStore.resetCityContext()
    attractionStore.resetAttractions()
    foodStore.resetFoodState()
  },
  { flush: 'sync' },
)
</script>
