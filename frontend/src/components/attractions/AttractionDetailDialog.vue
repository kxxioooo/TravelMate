<template>
  <el-dialog
    :model-value="Boolean(detail)"
    :title="detailTitle"
    width="720px"
    align-center
    @update:model-value="handleClose"
  >
    <div v-loading="loading" class="tm-attraction-detail">
      <div v-if="photos.length" class="tm-attraction-detail-photos">
        <el-image
          v-for="(url, index) in photos"
          :key="url"
          class="tm-attraction-detail-photo"
          :src="url"
          fit="cover"
          :preview-src-list="photos"
          :initial-index="index"
          preview-teleported
          :alt="detailTitle"
        >
          <template #error>
            <div class="tm-attraction-detail-photo-fallback">
              <el-icon><Picture /></el-icon>
            </div>
          </template>
        </el-image>
      </div>
      <p v-else class="tm-attraction-detail-no-photo">{{ t('attraction.detail_no_photo') }}</p>

      <el-descriptions class="tm-attraction-detail-info" :column="1" border>
        <el-descriptions-item :label="t('attraction.detail_address')">
          {{ addressText }}
        </el-descriptions-item>

        <el-descriptions-item :label="t('attraction.detail_cost')">
          {{ formatPrice(detail?.cost) }}
        </el-descriptions-item>

        <el-descriptions-item :label="t('attraction.detail_tags')">
          <template v-if="tags.length">
            <el-tag
              v-for="(tag, index) in tags"
              :key="`${tag}-${index}`"
              class="tm-attraction-detail-tag"
              size="small"
              effect="plain"
              round
            >
              {{ tag }}
            </el-tag>
          </template>
          <span v-else>{{ t('common.unknown') }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 后端即使返回 location,这里也绝不展示经纬度 -->
    </div>
  </el-dialog>
</template>

<script setup>
import { Picture } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { resolveLocalizedTags } from '../../constants/localizedTerms'
import { displayOrUnknown, formatPrice, safePhotoUrls } from '../../utils/display'
import { displayBilingualAddress, displayBilingualName } from '../../utils/i18nDisplay'

/**
 * 景点详情弹窗。
 *
 * 只展示:更多照片、地址、价格 / 门票、标签。
 * 英文模式下名称与地址都是 `English (中文)`;经纬度(location)即使后端
 * 返回也不在 UI 展示,价格 / 评分 / poi_id 等事实字段保持原值。
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

const tags = computed(() =>
  resolveLocalizedTags(props.detail?.tags, props.detail?.tags_en, locale.value, t),
)

/** 关闭弹窗,把意图交给父级。 */
function handleClose() {
  emit('close')
}
</script>

<style scoped>
.tm-attraction-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 120px;
}

.tm-attraction-detail-photos {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
}

.tm-attraction-detail-photo {
  width: 100%;
  height: 110px;
  border-radius: 10px;
}

.tm-attraction-detail-photo-fallback {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--tm-muted);
  background: var(--tm-page-bg);
}

.tm-attraction-detail-no-photo {
  margin: 0;
  font-size: 13px;
  color: var(--tm-muted);
}

.tm-attraction-detail-tag {
  margin-right: 6px;
}
</style>
