<template>
  <div class="tm-load-more">
    <el-button
      class="tm-load-more-btn"
      :loading="loading"
      :disabled="disabled || loading"
      plain
      @click="emitLoadMore"
    >
      {{ loading ? t('common.loading') : t('common.load_more') }}
    </el-button>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

/**
 * 通用 Load More 按钮。
 *
 * 纯交互组件:自己不发请求,点击后把意图抛给父级。
 */
defineProps({
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const { t } = useI18n()

const emit = defineEmits(['load-more'])

/** 点击后向上抛出加载更多意图。 */
function emitLoadMore() {
  emit('load-more')
}
</script>

<style scoped>
.tm-load-more {
  display: flex;
  justify-content: center;
  padding: 16px 0 4px;
}

.tm-load-more-btn {
  min-width: 140px;
}
</style>
