<template>
  <!--
    §25.5 Agent Activity:只渲染后端真实返回的活动。
    DOM 里只出现 status 图标与后端给的 text,不出现任何 prompt / 思维链 / tool payload(§34 / §43)。
  -->
  <ul class="tm-agent-activity">
    <li
      v-for="(activity, index) in activities"
      :key="`${activity.type}-${index}`"
      class="tm-activity-item"
      :class="`tm-activity-item--${activity.status}`"
    >
      <span class="tm-activity-icon" aria-hidden="true">{{ activityLabel(activity) }}</span>
      <span class="tm-activity-text">{{ activity.text }}</span>
    </li>
  </ul>
</template>

<script setup>
defineProps({
  activities: { type: Array, default: () => [] },
})

/** §25.5 success -> ✓ / running -> ● / error -> ! */
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
