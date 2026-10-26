<template>
  <el-dialog
    :model-value="Boolean(detail)"
    :title="detailTitle"
    width="620px"
    align-center
    @update:model-value="handleClose"
  >
    <div v-loading="loading" class="tm-restaurant-detail">
      <div v-if="photos.length" class="tm-restaurant-detail-photos">
        <el-image
          v-for="(url, index) in photos"
          :key="url"
          class="tm-restaurant-detail-photo"
          :src="url"
          fit="cover"
          :preview-src-list="photos"
          :initial-index="index"
          preview-teleported
          :alt="detailTitle"
        >
          <template #error>
            <div class="tm-restaurant-detail-photo-fallback">
              <el-icon><Picture /></el-icon>
            </div>
          </template>
        </el-image>
      </div>

      <el-descriptions class="tm-restaurant-detail-info" :column="1" border>
        <el-descriptions-item :label="t('restaurant.detail_cost')">
          {{ formatPrice(detail?.cost) }}
        </el-descriptions-item>

        <el-descriptions-item :label="t('restaurant.detail_address')">
          {{ addressText }}
        </el-descriptions-item>

        <el-descriptions-item :label="t('restaurant.detail_rating')">
          <span v-if="ratingText" class="tm-restaurant-detail-rating">{{ ratingText }}</span>
          <span v-else>{{ t('common.unknown') }}</span>
        </el-descriptions-item>

        <el-descriptions-item :label="t('restaurant.detail_telephone')">
          {{ displayOrUnknown(detail?.telephone) }}
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </el-dialog>
</template>

<script setup>
import { Picture } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { displayOrUnknown, formatPrice, safePhotoUrls } from '../../utils/display'
import { displayBilingualAddress, displayBilingualName } from '../../utils/i18nDisplay'

/**
 * 餐厅详情弹窗:人均 / 价格、地址、评分、预订电话。
 *
 * 英文模式名称与地址是 `English (中文)`;评分、价格、电话等数字 / 事实
 * 字段保持原值。第三方 API 没给的一律显示当前语言的"暂无信息",绝不猜。
 */
const props = defineProps({
  detail: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const { t, locale } = useI18n()

const photos = computed(() => safePhotoUrls(props.detail?.photos))

const detailTitle = computed(
  () =>
    displayBilingualName(props.detail?.name, props.detail?.name_en, locale.value) ||
    displayOrUnknown(null),
)

const addressText = computed(
  () =>
    displayBilingualAddress(props.detail?.address, props.detail?.address_en, locale.value) ||
    displayOrUnknown(props.detail?.address),
)

const ratingText = computed(() => {
  const rating = Number(props.detail?.rating)
  return Number.isFinite(rating) && rating > 0 ? rating.toFixed(1) : ''
})

/** 关闭弹窗,把意图交给父级。 */
function handleClose() {
  emit('close')
}
</script>

<style scoped>
.tm-restaurant-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100px;
}

.tm-restaurant-detail-photos {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
}

.tm-restaurant-detail-photo {
  width: 100%;
  height: 96px;
  border-radius: 10px;
}

.tm-restaurant-detail-photo-fallback {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--tm-muted);
  background: var(--tm-page-bg);
}

.tm-restaurant-detail-rating {
  font-weight: 600;
  color: var(--tm-accent);
}
</style>
