<template>
  <article class="tm-attraction-card">
    <div class="tm-attraction-card-cover">
      <el-image
        v-if="coverUrl"
        class="tm-attraction-card-image"
        :src="coverUrl"
        fit="cover"
        :alt="attractionName"
      >
        <template #error>
          <div class="tm-attraction-card-placeholder">
            <el-icon><Picture /></el-icon>
          </div>
        </template>
        <template #placeholder>
          <div class="tm-attraction-card-placeholder">
            <el-icon><Picture /></el-icon>
          </div>
        </template>
      </el-image>
      <div v-else class="tm-attraction-card-placeholder">
        <el-icon><Picture /></el-icon>
        <span>{{ t('common.no_image') }}</span>
      </div>
    </div>

    <div class="tm-attraction-card-body">
      <h3 class="tm-attraction-card-name">{{ attractionName }}</h3>

      <div v-if="hasRating" class="tm-attraction-card-rating">
        <el-rate :model-value="attraction.rating" disabled allow-half size="small" />
        <span class="tm-attraction-card-score">{{ ratingText }}</span>
      </div>
      <p v-else class="tm-attraction-card-no-rating">{{ t('attraction.no_rating') }}</p>

      <div class="tm-attraction-card-tags">
        <template v-if="tags.length">
          <el-tag
            v-for="(tag, index) in tags"
            :key="`${tag}-${index}`"
            class="tm-attraction-card-tag"
            size="small"
            effect="plain"
            round
          >
            {{ tag }}
          </el-tag>
        </template>
        <span v-else class="tm-attraction-card-no-tag">{{ t('attraction.no_tag') }}</span>
      </div>

      <div class="tm-attraction-card-footer">
        <el-button class="tm-attraction-detail-btn" type="primary" plain @click="openDetail">
          {{ t('attraction.detail_button') }}
        </el-button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { Picture } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { resolveLocalizedTags } from '../../constants/localizedTerms'
import { displayOrUnknown, safePhotoUrls } from '../../utils/display'
import { displayBilingualName } from '../../utils/i18nDisplay'

/**
 * 景点卡片:封面图 + 名称 + 评分(有则显示) + 标签 + 详情按钮。
 *
 * 英文模式名称是 `West Lake (西湖)`;评分、poi_id、图片 URL 等事实字段
 * 永远保持原值。卡片自己不请求接口,详情交给父级 → store。
 */
const props = defineProps({
  attraction: { type: Object, required: true },
})

const emit = defineEmits(['open-detail'])

const { t, locale } = useI18n()

/** 后端给的是网络图片 URL,这里做空值 / 重复 / 非法过滤。 */
const coverUrl = computed(() => safePhotoUrls(props.attraction?.cover_photo)[0] ?? '')

/** 双语名称:有英文名才加括号中文,没有英文名不伪造。 */
const attractionName = computed(
  () =>
    displayBilingualName(props.attraction?.name, props.attraction?.name_en, locale.value) ||
    displayOrUnknown(null),
)

const hasRating = computed(() => Number.isFinite(props.attraction?.rating) && props.attraction.rating > 0)

const ratingText = computed(() => (hasRating.value ? Number(props.attraction.rating).toFixed(1) : ''))

/** 标签:优先后端 `tags_en`,否则走已审核的分类映射,未收录的保留高德原文。 */
const tags = computed(() =>
  resolveLocalizedTags(
    props.attraction?.tags,
    props.attraction?.tags_en,
    locale.value,
    t,
  ),
)

/** 向上抛出详情意图,不直接请求 API。 */
function openDetail() {
  if (!props.attraction?.poi_id) {
    return
  }

  emit('open-detail', props.attraction.poi_id)
}
</script>

<style scoped>
.tm-attraction-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--tm-surface);
  border: 1px solid var(--tm-border);
  border-radius: var(--tm-radius);
  box-shadow: var(--tm-shadow-sm);
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}

.tm-attraction-card:hover {
  box-shadow: var(--tm-shadow-md);
  transform: translateY(-2px);
}

.tm-attraction-card-cover {
  height: 148px;
  background: var(--tm-page-bg);
}

.tm-attraction-card-image {
  width: 100%;
  height: 100%;
}

.tm-attraction-card-placeholder {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: var(--tm-muted);
  background: repeating-linear-gradient(45deg, #f2f6f5, #f2f6f5 10px, #eaf1ef 10px, #eaf1ef 20px);
}

.tm-attraction-card-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px 14px;
}

.tm-attraction-card-name {
  margin: 0;
  overflow: hidden;
  font-size: 15px;
  font-weight: 600;
  color: var(--tm-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tm-attraction-card-rating {
  display: flex;
  gap: 8px;
  align-items: center;
}

.tm-attraction-card-score {
  font-size: 13px;
  font-weight: 600;
  color: var(--tm-accent);
}

.tm-attraction-card-no-rating,
.tm-attraction-card-no-tag {
  margin: 0;
  font-size: 12px;
  color: var(--tm-muted);
}

.tm-attraction-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 22px;
}

.tm-attraction-card-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: auto;
}
</style>
