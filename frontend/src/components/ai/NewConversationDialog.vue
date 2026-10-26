<template>
  <!--
    §4 / §20 新建与编辑会话城市。
    默认隐藏(只 v-show 切换),根节点 class 供验收脚本直接定位。
    标题 / 按钮 / 提示全部走 i18n,城市选择器内部按当前语言显示双语城市名。
  -->
  <div
    v-show="modelValue"
    class="tm-new-conversation-dialog"
    role="dialog"
    aria-modal="true"
    :aria-label="dialogTitle"
  >
    <div class="tm-dialog-backdrop" @click="handleCancel" />

    <section class="tm-dialog-card">
      <header class="tm-dialog-header">
        <h3 class="tm-dialog-title">{{ dialogTitle }}</h3>
        <p class="tm-dialog-hint">{{ t('conversation.create_hint') }}</p>
      </header>

      <ConversationCitySelector
        v-model:keyword="keyword"
        :selected-cities="selectedCities"
        @toggle-city="toggleCity"
        @remove-city="toggleCity"
      />

      <footer class="tm-dialog-footer">
        <el-button class="tm-cancel-conversation-btn" @click="handleCancel">
          {{ t('conversation.cancel') }}
        </el-button>
        <el-button
          type="primary"
          class="tm-create-conversation-btn"
          :loading="isSubmitting"
          @click="handleCreate"
        >
          {{ isEdit ? t('conversation.save') : t('conversation.create') }}
        </el-button>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useConversationStore } from '../../stores/conversations'
import ConversationCitySelector from './ConversationCitySelector.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** create:新建会话;edit:修改当前会话城市(§45)。 */
  mode: { type: String, default: 'create' },
  initialCities: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'created', 'updated'])

const { t } = useI18n()

const conversationStore = useConversationStore()

const isEdit = computed(() => props.mode === 'edit')

/** 弹窗标题随模式切换:新建旅行会话 / 编辑旅行城市。 */
const dialogTitle = computed(() =>
  isEdit.value ? t('conversation.edit_title') : t('conversation.create_title'),
)

const keyword = ref('')
const selectedCities = ref([])
const isSubmitting = ref(false)

/** §20.4 重置表单:selectedCities = [] 且 keyword = ""。 */
function resetForm() {
  selectedCities.value = []
  keyword.value = ''
}

/** §20.1 按 adcode 判重:已存在则移除,不存在则加入。 */
function toggleCity(city) {
  const cityName = String(city?.city_name ?? '').trim()
  if (!cityName) {
    return
  }

  const adcode = city?.adcode === null || city?.adcode === undefined ? '' : String(city.adcode)
  const exists = selectedCities.value.some((item) => String(item.adcode) === adcode)

  if (exists) {
    selectedCities.value = selectedCities.value.filter((item) => String(item.adcode) !== adcode)
    return
  }

  selectedCities.value = [...selectedCities.value, { city_name: cityName, adcode }]
  // 选完立刻清空搜索词,避免旧候选一直停在下面。
  keyword.value = ''
}

/** §20.2 允许 selectedCities = [];创建 / 编辑都只走 Conversation Store。 */
async function handleCreate() {
  if (isSubmitting.value) {
    return
  }

  // 只把中文名 + adcode 写库,绝不把 `Xi'an (西安)` 这类展示文本存进去。
  const cities = selectedCities.value.map((city) => ({
    city_name: city.city_name,
    adcode: city.adcode,
  }))

  isSubmitting.value = true

  try {
    const conversation = isEdit.value
      ? await conversationStore.updateCities(cities)
      : await conversationStore.createNewConversation(cities)

    // 失败时保持弹窗打开,用户可以直接重试。
    if (!conversation) {
      return
    }

    emit(isEdit.value ? 'updated' : 'created', conversation)
    emit('update:modelValue', false)
    resetForm()
  } finally {
    isSubmitting.value = false
  }
}

/** §20.3 取消:关闭并重置。 */
function handleCancel() {
  emit('update:modelValue', false)
  resetForm()
}

/**
 * 每次打开都重新开始:
 * - 新建模式:从空表单开始;
 * - 编辑模式:回显当前 Conversation 的城市(§45 允许修改会话城市)。
 */
watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      return
    }

    resetForm()

    if (!isEdit.value) {
      return
    }

    selectedCities.value = (Array.isArray(props.initialCities) ? props.initialCities : [])
      .filter((city) => city && city.city_name)
      .map((city) => ({
        city_name: String(city.city_name),
        adcode: city.adcode === null || city.adcode === undefined ? '' : String(city.adcode),
      }))
  },
  { immediate: true },
)
</script>

<style scoped>
.tm-new-conversation-dialog {
  position: fixed;
  inset: 0;
  z-index: 2600;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.tm-dialog-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(16, 48, 45, 0.35);
}

.tm-dialog-card {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: min(560px, 100%);
  padding: 22px;
  background: var(--tm-surface);
  border-radius: var(--tm-radius-lg);
  box-shadow: var(--tm-shadow-lg);
}

.tm-dialog-title {
  margin: 0 0 6px;
  font-size: 17px;
  font-weight: 600;
  color: var(--tm-ink);
}

.tm-dialog-hint {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--tm-muted);
}

.tm-dialog-footer {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>
