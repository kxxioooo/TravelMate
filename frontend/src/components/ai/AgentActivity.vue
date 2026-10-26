<template>
  <!--
    Agent Activity:只渲染后端真实返回的活动。
    展示来源是 `code + params`(本地化),`text` 仅作向后兼容兜底;
    DOM 里不出现任何 prompt / 思维链 / tool payload。
  -->
  <ul class="tm-agent-activity" :aria-label="t('activity.aria_label')">
    <li
      v-for="(activity, index) in activities"
      :key="`${activity.type}-${index}`"
      class="tm-activity-item"
      :class="`tm-activity-item--${activity.status}`"
    >
      <span class="tm-activity-icon" aria-hidden="true">{{ activityLabel(activity) }}</span>
      <span class="tm-activity-text">{{ activityText(activity) }}</span>
    </li>
  </ul>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

import { displayCityName } from '../../utils/i18nDisplay'

defineProps({
  activities: { type: Array, default: () => [] },
})

const { t, te, locale } = useI18n()

/** success -> ✓ / running -> ● / error -> ! */
function activityLabel(activity) {
  const status = activity?.status

  if (status === 'running') {
    return '●'
  }

  if (status === 'error') {
    return '!'
  }

  return '✓'
}

/**
 * 活动参数:城市按 `English (中文)` 展示,关键词保持后端原文(不翻译)。
 *
 * params 里只有原始中文 / ID,所以这里只做"城市名双语格式化",
 * 绝不改写 keyword 或 adcode。
 */
function activityParams(activity) {
  const params = activity?.params ?? {}
  const hasCity = Boolean(params.city_name || params.city_adcode)
  const city = hasCity
    ? displayCityName(
        { city_name: params.city_name ?? '', adcode: params.city_adcode ?? '' },
        locale.value,
      )
    : ''

  return {
    city: city || t('common.unknown'),
    keyword: typeof params.keyword === 'string' ? params.keyword : '',
  }
}

/**
 * 活动文案。
 *
 * 有 `code` 就按 `activity.<code>` 本地化(契约 §4),
 * `agent.food_found` 带 keyword 时用"相关餐厅"变体;
 * 没有 code(老后端)才退回后端 `text`,绝不凭空造活动。
 */
function activityText(activity) {
  const code = typeof activity?.code === 'string' ? activity.code.trim() : ''

  if (code) {
    const params = activityParams(activity)
    const key =
      code === 'agent.food_found' && params.keyword
        ? 'activity.agent.food_found_keyword'
        : `activity.${code}`

    if (te(key)) {
      return t(key, params)
    }
  }

  return activity?.text ?? ''
}
</script>

<style scoped>
.tm-agent-activity {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 0 0;
  margin: 0;
  list-style: none;
}

.tm-activity-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  font-size: 12.5px;
  color: var(--tm-muted);
}

.tm-activity-icon {
  flex: none;
  width: 12px;
  font-weight: 700;
  text-align: center;
}

.tm-activity-item--success .tm-activity-icon {
  color: var(--tm-primary);
}

.tm-activity-item--running .tm-activity-icon {
  color: var(--tm-accent);
}

.tm-activity-item--error .tm-activity-icon {
  color: #c45656;
}

.tm-activity-text {
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
