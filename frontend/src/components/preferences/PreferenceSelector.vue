<template>
  <div class="tm-selector">
    <section class="tm-selector-block">
      <h3 class="tm-section-title">{{ t('onboarding.section_attraction') }}</h3>
      <div class="tm-chips">
        <el-check-tag
          v-for="item in ATTRACTION_PREFERENCES"
          :key="item"
          :checked="draft.attraction_preferences.includes(item)"
          class="tm-chip"
          @change="toggleAttractionPreference(item)"
        >
          <!-- 显示用当前语言的标签,`:key` / 选中判断 / emit 仍是原始中文值 -->
          {{ preferenceLabel(item, t) }}
        </el-check-tag>
      </div>
    </section>

    <section class="tm-selector-block">
      <h3 class="tm-section-title">{{ t('onboarding.section_food') }}</h3>
      <div class="tm-chips">
        <el-check-tag
          v-for="item in FOOD_PREFERENCES"
          :key="item"
          :checked="draft.food_preferences.includes(item)"
          class="tm-chip"
          @change="toggleFoodPreference(item)"
        >
          {{ preferenceLabel(item, t) }}
        </el-check-tag>
      </div>
    </section>

    <section class="tm-selector-block">
      <h3 class="tm-section-title">{{ t('onboarding.section_budget') }}</h3>
      <el-radio-group :model-value="draft.budget" @change="selectBudget">
        <el-radio-button v-for="item in BUDGET_OPTIONS" :key="item" :value="item">
          {{ preferenceLabel(item, t) }}
        </el-radio-button>
      </el-radio-group>
    </section>

    <section class="tm-selector-block">
      <h3 class="tm-section-title">{{ t('onboarding.section_pace') }}</h3>
      <el-radio-group :model-value="draft.travel_pace" @change="selectTravelPace">
        <el-radio-button v-for="item in TRAVEL_PACE_OPTIONS" :key="item" :value="item">
          {{ preferenceLabel(item, t) }}
        </el-radio-button>
      </el-radio-group>
    </section>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  ATTRACTION_PREFERENCES,
  BUDGET_OPTIONS,
  FOOD_PREFERENCES,
  TRAVEL_PACE_OPTIONS,
  preferenceLabel,
} from '../../constants/preferences'

/**
 * 偏好选择器。
 *
 * v0.3.1 关键约束:数组元素是**落库值**(中文原字面量),
 * 这里只用 `preferenceLabel()` 做显示翻译;`:key`、`includes()` 判断、
 * emit 出去的对象全部保持原始中文值,不会污染 v0.3 的数据与后端校验。
 */
const props = defineProps({
  modelValue: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue'])

const { t } = useI18n()

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

/** 统一向父组件发送完整结构(值不变,仍是中文原字面量)。 */
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
