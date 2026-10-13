<template>
  <div class="tm-selector">
    <section class="tm-selector-block">
      <h3 class="tm-section-title">景点偏好</h3>
      <div class="tm-chips">
        <el-check-tag
          v-for="item in ATTRACTION_PREFERENCES"
          :key="item"
          :checked="draft.attraction_preferences.includes(item)"
          class="tm-chip"
          @change="toggleAttractionPreference(item)"
        >
          {{ item }}
        </el-check-tag>
      </div>
    </section>

    <section class="tm-selector-block">
      <h3 class="tm-section-title">饮食偏好</h3>
      <div class="tm-chips">
        <el-check-tag
          v-for="item in FOOD_PREFERENCES"
          :key="item"
          :checked="draft.food_preferences.includes(item)"
          class="tm-chip"
          @change="toggleFoodPreference(item)"
        >
          {{ item }}
        </el-check-tag>
      </div>
    </section>

    <section class="tm-selector-block">
      <h3 class="tm-section-title">预算</h3>
      <el-radio-group :model-value="draft.budget" @change="selectBudget">
        <el-radio-button v-for="item in BUDGET_OPTIONS" :key="item" :value="item">
          {{ item }}
        </el-radio-button>
      </el-radio-group>
    </section>

    <section class="tm-selector-block">
      <h3 class="tm-section-title">旅行节奏</h3>
      <el-radio-group :model-value="draft.travel_pace" @change="selectTravelPace">
        <el-radio-button v-for="item in TRAVEL_PACE_OPTIONS" :key="item" :value="item">
          {{ item }}
        </el-radio-button>
      </el-radio-group>
    </section>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

import {
  ATTRACTION_PREFERENCES,
  BUDGET_OPTIONS,
  FOOD_PREFERENCES,
  TRAVEL_PACE_OPTIONS,
} from '../../constants/preferences'

const props = defineProps({
  modelValue: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue'])

const draft = reactive({
  attraction_preferences: [...(props.modelValue.attraction_preferences ?? [])],
  food_preferences: [...(props.modelValue.food_preferences ?? [])],
  budget: props.modelValue.budget ?? null,
  travel_pace: props.modelValue.travel_pace ?? null,
})

// 父组件异步回显偏好时同步进来(Onboarding 先渲染再拉数据)
watch(
  () => props.modelValue,
  (next) => {
    draft.attraction_preferences = [...(next.attraction_preferences ?? [])]
    draft.food_preferences = [...(next.food_preferences ?? [])]
    draft.budget = next.budget ?? null
    draft.travel_pace = next.travel_pace ?? null
  },
  { deep: true },
)

/** 切换景点偏好。 */
function toggleAttractionPreference(value) {
  const index = draft.attraction_preferences.indexOf(value)
  if (index >= 0) {
    draft.attraction_preferences.splice(index, 1)
  } else {
    draft.attraction_preferences.push(value)
  }
  emitValue()
}

/** 切换饮食偏好。 */
function toggleFoodPreference(value) {
  const index = draft.food_preferences.indexOf(value)
  if (index >= 0) {
    draft.food_preferences.splice(index, 1)
  } else {
    draft.food_preferences.push(value)
  }
  emitValue()
}

/** 设置预算;点已选中的项可取消。 */
function selectBudget(value) {
  draft.budget = draft.budget === value ? null : value
  emitValue()
}

/** 设置旅行节奏;点已选中的项可取消。 */
function selectTravelPace(value) {
  draft.travel_pace = draft.travel_pace === value ? null : value
  emitValue()
}

/** 统一向父组件发送完整结构。 */
function emitValue() {
  emit('update:modelValue', {
    attraction_preferences: [...draft.attraction_preferences],
    food_preferences: [...draft.food_preferences],
    budget: draft.budget,
    travel_pace: draft.travel_pace,
  })
}
</script>

<style scoped>
.tm-selector {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.tm-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.tm-chip {
  padding: 6px 14px;
  font-size: 13px;
  border-radius: 999px;
}
</style>
