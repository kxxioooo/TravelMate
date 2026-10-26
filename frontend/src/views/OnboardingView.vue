<template>
  <div class="tm-onboarding">
    <!-- Onboarding 也没有主站顶部栏:语言切换固定在右上角 -->
    <LanguageSwitcher position="fixed" />

    <div class="tm-onboarding-card">
      <header class="tm-onboarding-header">
        <div>
          <h1 class="tm-onboarding-title">{{ t('onboarding.title') }}</h1>
          <p class="tm-onboarding-subtitle">{{ t('onboarding.subtitle') }}</p>
        </div>
        <el-button v-if="authStore.user?.onboarding_completed" text @click="goHome">
          {{ t('onboarding.back_home') }}
        </el-button>
      </header>

      <PreferenceSelector v-model="draft" />

      <footer class="tm-onboarding-footer">
        <el-button size="large" text :loading="preferencesStore.isSaving" @click="handleSkip">
          {{ t('onboarding.skip') }}
        </el-button>
        <el-button
          type="primary"
          size="large"
          :loading="preferencesStore.isSaving"
          @click="handleSave"
        >
          {{ t('onboarding.save') }}
        </el-button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import LanguageSwitcher from '../components/common/LanguageSwitcher.vue'
import PreferenceSelector from '../components/preferences/PreferenceSelector.vue'
import { useAuthStore } from '../stores/auth'
import { usePreferencesStore } from '../stores/preferences'
import { formatLocalizedError } from '../utils/i18nDisplay'

const { t } = useI18n()

const router = useRouter()
const authStore = useAuthStore()
const preferencesStore = usePreferencesStore()

/**
 * 偏好草稿的真实形状:**落库值仍是中文原字面量**(如 `自然风景`),
 * 英文化只发生在 PreferenceSelector 的显示层。
 * 用 ref 而不是 reactive:PreferenceSelector 通过 v-model 抛出的是整体新对象。
 */
const draft = ref({
  attraction_preferences: [],
  food_preferences: [],
  budget: null,
  travel_pace: null,
})

/** 回显已有偏好:首次进来是空结构,老用户进来是上次保存的内容。 */
async function loadExistingPreferences() {
  try {
    const data = await preferencesStore.loadPreferences()
    draft.value = {
      attraction_preferences: [...(data.attraction_preferences ?? [])],
      food_preferences: [...(data.food_preferences ?? [])],
      budget: data.budget ?? null,
      travel_pace: data.travel_pace ?? null,
    }
  } catch (error) {
    ElMessage.error(
      formatLocalizedError(error?.normalized ?? { status: 0 }, {
        t,
        fallbackKey: 'onboarding.load_failed',
      }),
    )
  }
}

/** 保存偏好(值不变,只换显示),并把 onboarding_completed 同步到本地状态。 */
async function handleSave() {
  try {
    await preferencesStore.savePreferences({
      attraction_preferences: [...draft.value.attraction_preferences],
      food_preferences: [...draft.value.food_preferences],
      budget: draft.value.budget,
      travel_pace: draft.value.travel_pace,
    })
    authStore.setOnboardingCompleted(true)
    ElMessage.success(t('onboarding.saved'))
    goHome()
  } catch (error) {
    ElMessage.error(
      formatLocalizedError(error?.normalized ?? { status: 0 }, {
        t,
        fallbackKey: 'onboarding.save_failed',
      }),
    )
  }
}

/** Skip:只标记完成,不伪造偏好。 */
async function handleSkip() {
  try {
    const user = await preferencesStore.skipPreferences()
    authStore.setOnboardingCompleted(user?.onboarding_completed ?? true)
    goHome()
  } catch (error) {
    ElMessage.error(
      formatLocalizedError(error?.normalized ?? { status: 0 }, {
        t,
        fallbackKey: 'onboarding.skip_failed',
      }),
    )
  }
}

/** 统一完成页面跳转。 */
function goHome() {
  router.push({ name: 'home' })
}

onMounted(loadExistingPreferences)
</script>

<style scoped>
.tm-onboarding {
  display: flex;
  justify-content: center;
  min-height: 100vh;
  padding: 40px 16px;
  background: var(--tm-page-bg);
}

.tm-onboarding-card {
  display: flex;
  flex-direction: column;
  gap: 28px;
  width: 100%;
  max-width: 760px;
  padding: 32px;
  background: var(--tm-surface);
  border-radius: var(--tm-radius-lg);
  box-shadow: var(--tm-shadow-md);
}

.tm-onboarding-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.tm-onboarding-title {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 700;
  color: var(--tm-primary-dark);
}

.tm-onboarding-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--tm-muted);
}

.tm-onboarding-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--tm-border);
}

@media (max-width: 640px) {
  .tm-onboarding-card {
    padding: 22px 18px;
  }
}
</style>
