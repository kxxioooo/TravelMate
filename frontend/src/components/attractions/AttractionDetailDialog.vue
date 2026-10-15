<template>
  <el-dialog
    :model-value="Boolean(detail)"
    :title="displayOrUnknown(detail?.name)"
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
          alt=""
        >
          <template #error>
            <div class="tm-attraction-detail-photo-fallback">
              <el-icon><Picture /></el-icon>
            </div>
          </template>
        </el-image>
      </div>
      <p v-else class="tm-attraction-detail-no-photo">图片:暂无信息</p>

      <el-descriptions class="tm-attraction-detail-info" :column="1" border>
        <el-descriptions-item label="地址">
          {{ displayOrUnknown(detail?.address) }}
        </el-descriptions-item>

        <el-descriptions-item label="价格 / 门票">
          {{ formatPrice(detail?.cost) }}
        </el-descriptions-item>

        <el-descriptions-item label="标签">
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
          <span v-else>暂无信息</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 后端即使返回 location,这里也绝不展示经纬度 -->
    </div>
  </el-dialog>
</template>

<script setup>
import { Picture } from '@element-plus/icons-vue'
import { computed } from 'vue'

import { displayOrUnknown, formatPrice, safePhotoUrls } from '../../utils/display'

/**
 * 景点详情弹窗。
 *
 * 只展示:更多照片、地址、价格 / 门票、标签。
 * 经纬度(location)即使后端返回也不在 UI 展示。
 */
const props = defineProps({
  detail: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const photos = computed(() => safePhotoUrls(props.detail?.photos))

const tags = computed(() =>
  Array.isArray(props.detail?.tags)
    ? props.detail.tags.filter((tag) => typeof tag === 'string' && tag.trim())
    : [],
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
