<template>
  <div class="tm-onboarding">
    <div class="tm-onboarding-card">
      <header class="tm-onboarding-header">
        <div>
          <h1 class="tm-onboarding-title">Tell us what you like</h1>
          <p class="tm-onboarding-subtitle">
            选得越具体,后续的行程建议越贴近你。也可以直接 Skip。
          </p>
        </div>
        <el-button v-if="authStore.user?.onboarding_completed" text @click="goHome">
          返回首页
        </el-button>
      </header>

      <PreferenceSelector v-model="draft" />

      <footer class="tm-onboarding-footer">
        <el-button size="large" text :loading="preferencesStore.isSaving" @click="handleSkip">
          Skip
        </el-button>
        <el-button
          type="primary"
          size="large"
          :loading="preferencesStore.isSaving"
          @click="handleSave"
        >
          Save
        </el-button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import PreferenceSelector from '../components/preferences/PreferenceSelector.vue'
import { useAuthStore } from '../stores/auth'
import { usePreferencesStore } from '../stores/preferences'

const router = useRouter()
const authStore = useAuthStore()
const preferencesStore = usePreferencesStore()

// 用 ref 而不是 reactive:PreferenceSelector 通过 v-model 抛出的是整体新对象,
// const + reactive 无法被重新赋值(编译器只能替你悄悄改成 let),
// 结果第一次 emit 之后 draft 就退化成普通对象。ref 才是这里正确的形状。
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
    ElMessage.error(error.normalized?.message ?? '偏好读取失败')
  }
}

/** 保存偏好,并把 onboarding_completed 同步到本地状态。 */
async function handleSave() {
  try {
    await preferencesStore.savePreferences({
      attraction_preferences: [...draft.value.attraction_preferences],
      food_preferences: [...draft.value.food_preferences],
      budget: draft.value.budget,
      travel_pace: draft.value.travel_pace,
    })
    authStore.setOnboardingCompleted(true)
    ElMessage.success('偏好已保存')
    goHome()
  } catch (error) {
    ElMessage.error(error.normalized?.message ?? '保存偏好失败')
  }
}

/** Skip:只标记完成,不伪造偏好。 */
async function handleSkip() {
  try {
    const user = await preferencesStore.skipPreferences()
    authStore.setOnboardingCompleted(user?.onboarding_completed ?? true)
    goHome()
  } catch (error) {
    ElMessage.error(error.normalized?.message ?? '操作失败,请稍后重试')
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
