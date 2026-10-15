<template>
  <MainLayout
    :selected-city="cityStore.selectedCity"
    @city-selected="handleCitySelected"
    @open-preferences="handleOpenPreferences"
    @open-prompts="handleOpenPrompts"
    @open-settings="handleOpenSettings"
  >
    <!--
      §3.1 还没搜索 / 选中城市:真实 ChatPanel 直接占主页主要区域。
      注意:这里与下面的城市布局是 v-if 切换,不是常驻占位 —— ChatPanel 会被
      重新挂载,所以 draft / messages / activities 全部放在 store 里。
    -->
    <div v-if="!cityStore.selectedCity" class="tm-home-chat">
      <ChatPanel ref="chatPanelRef" />
    </div>

    <!-- §3.2 选中城市:保留 v0.2 的 80/20 可拖动 Splitter,右侧换成真实 ChatPanel -->
    <CityWorkspace
      v-else
      :city="cityStore.selectedCity"
      :weather="cityStore.weather"
      :clothing-advice="cityStore.clothingAdvice"
      :weather-loading="cityStore.isWeatherLoading"
      :username="authStore.user?.username ?? ''"
    >
      <template #ai>
        <ChatPanel ref="chatPanelRef" />
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

import ChatPanel from '../components/ai/ChatPanel.vue'
import CityWorkspace from '../components/city/CityWorkspace.vue'
import RecommendedPromptsPanel from '../components/home/RecommendedPromptsPanel.vue'
import SettingsPanel from '../components/home/SettingsPanel.vue'
import MainLayout from '../components/layout/MainLayout.vue'
import { useAttractionStore } from '../stores/attractions'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { useCityStore } from '../stores/city'
import { useConversationStore } from '../stores/conversations'
import { useFoodStore } from '../stores/food'

const router = useRouter()
const authStore = useAuthStore()
const cityStore = useCityStore()
const attractionStore = useAttractionStore()
const foodStore = useFoodStore()
const conversationStore = useConversationStore()
const chatStore = useChatStore()

const activePanel = ref(null)
/** 两种布局下只有一侧处于挂载状态,ref 始终指向当前真实存在的 ChatPanel。 */
const chatPanelRef = ref(null)

/**
 * 选中城市后的统一入口。
 *
 * - 城市上下文(浏览历史 + 天气)全部由 cityStore.openCity 负责;
 * - 天气与默认 10 个景点并行获取(§3 用户流程);
 * - 这里刻意不加载十大美食:默认 Tab 是景点,美食等用户第一次
 *   切到"美食" Tab 再加载;
 * - §40:这里只动 cityStore,绝不触碰 Conversation 的绑定城市。
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

/**
 * §9 / §39 把静态 Prompt 交给真实 ChatPanel:只填入 ChatInput,不自动发送。
 *
 * 主路径是 ChatPanel.applyRecommendedPrompt();它万一还没挂载,就直接写
 * store 的 draftPrompt —— ChatPanel 挂载时会读一次,效果完全一致。
 */
function handlePromptSelected(prompt) {
  if (chatPanelRef.value) {
    chatPanelRef.value.applyRecommendedPrompt(prompt)
  } else {
    chatStore.setDraftPrompt(prompt)
  }

  closeActivePanel()
}

/** 关闭当前 Drawer / Dialog。 */
function closeActivePanel() {
  activePanel.value = null
}

/**
 * 退出登录时清空页面上下文与全部会话状态。
 *
 * AppSidebar 只负责清 auth / preferences,城市与会话相关状态在这里跟随
 * 登录态一起清掉,避免下一个账号看到上一个账号的城市 / 会话(§18.7 / §24.6)。
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
    conversationStore.resetConversations()
    chatStore.resetChat()
  },
  { flush: 'sync' },
)
</script>

<style scoped>
/*
 * 未选城市时 ChatPanel 撑满主内容区(不是 v0.2 的 20% 侧栏)。
 * 高度算法与 .tm-content--workspace .tm-splitter 保持一致。
 */
.tm-home-chat {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--tm-topbar-height) - var(--tm-content-gutter-y));
  min-height: 520px;
}
</style>
