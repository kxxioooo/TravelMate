<template>
  <article class="tm-attraction-card">
    <div class="tm-attraction-card-cover">
      <el-image
        v-if="coverUrl"
        class="tm-attraction-card-image"
        :src="coverUrl"
        fit="cover"
        alt=""
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
        <span>暂无图片</span>
      </div>
    </div>

    <div class="tm-attraction-card-body">
      <h3 class="tm-attraction-card-name">{{ displayOrUnknown(attraction?.name) }}</h3>

      <div v-if="hasRating" class="tm-attraction-card-rating">
        <el-rate :model-value="attraction.rating" disabled allow-half size="small" />
        <span class="tm-attraction-card-score">{{ ratingText }}</span>
      </div>
      <p v-else class="tm-attraction-card-no-rating">评分:暂无信息</p>

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
        <span v-else class="tm-attraction-card-no-tag">标签:暂无信息</span>
      </div>

      <div class="tm-attraction-card-footer">
        <el-button class="tm-attraction-detail-btn" type="primary" plain @click="openDetail">
          详情
        </el-button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { Picture } from '@element-plus/icons-vue'
import { computed } from 'vue'

import { displayOrUnknown, safePhotoUrls } from '../../utils/display'

/**
 * 景点卡片:封面图 + 名称 + 评分(有则显示) + 标签 + 详情按钮。
 *
 * 卡片自己不请求接口,详情交给父级 → store。
 */
const props = defineProps({
  attraction: { type: Object, required: true },
})

const emit = defineEmits(['open-detail'])

/** 后端给的是网络图片 URL,这里做空值 / 重复 / 非法过滤。 */
const coverUrl = computed(() => safePhotoUrls(props.attraction?.cover_photo)[0] ?? '')

const hasRating = computed(() => Number.isFinite(props.attraction?.rating) && props.attraction.rating > 0)

const ratingText = computed(() => (hasRating.value ? Number(props.attraction.rating).toFixed(1) : ''))

const tags = computed(() =>
  Array.isArray(props.attraction?.tags)
    ? props.attraction.tags.filter((tag) => typeof tag === 'string' && tag.trim())
    : [],
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
