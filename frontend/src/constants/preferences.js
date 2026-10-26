/**
 * 偏好选项的唯一来源。
 *
 * 所有 Vue 文件都从这里取值,不允许把选项再抄一遍 ——
 * 否则想加一个标签就要满仓库搜索。
 *
 * ===== v0.3.1 关键约束(跨端契约 / 规格 §7.2)=====
 * 这里导出的数组元素是**落库值**(中文原字面量),v0.3 的数据库、后端校验和
 * Agent 都按这些字面量工作。英文化只改"显示",不改"值":
 *   - 显示:`preferenceLabel('自然风景', t)` -> `Nature & scenery`;
 *   - 保存 / emit / 请求体:永远是 `'自然风景'`。
 * 因此绝对不能把数组元素换成 code 或英文,否则会破坏已有数据。
 */

export const ATTRACTION_PREFERENCES = [
  '自然风景',
  '历史文化',
  '博物馆',
  '古镇',
  '现代都市',
  '建筑',
  '主题乐园',
  '户外运动',
]

export const FOOD_PREFERENCES = ['辣', '清淡', '甜食', '海鲜', '烧烤', '火锅', '面食', '当地特色']

export const BUDGET_OPTIONS = ['经济', '普通', '高品质']

export const TRAVEL_PACE_OPTIONS = ['悠闲', '适中', '紧凑']

/** 景点偏好 -> i18n key(仅显示用)。 */
export const ATTRACTION_PREFERENCE_KEYS = {
  自然风景: 'prefs.attraction.nature',
  历史文化: 'prefs.attraction.history',
  博物馆: 'prefs.attraction.museum',
  古镇: 'prefs.attraction.ancient_town',
  现代都市: 'prefs.attraction.modern_city',
  建筑: 'prefs.attraction.architecture',
  主题乐园: 'prefs.attraction.theme_park',
  户外运动: 'prefs.attraction.outdoor',
}

/** 饮食偏好 -> i18n key(仅显示用)。 */
export const FOOD_PREFERENCE_KEYS = {
  辣: 'prefs.food.spicy',
  清淡: 'prefs.food.light',
  甜食: 'prefs.food.sweet',
  海鲜: 'prefs.food.seafood',
  烧烤: 'prefs.food.bbq',
  火锅: 'prefs.food.hotpot',
  面食: 'prefs.food.noodles',
  当地特色: 'prefs.food.local',
}

/** 预算 -> i18n key(仅显示用)。 */
export const BUDGET_KEYS = {
  经济: 'prefs.budget.economy',
  普通: 'prefs.budget.standard',
  高品质: 'prefs.budget.premium',
}

/** 旅行节奏 -> i18n key(仅显示用)。 */
export const TRAVEL_PACE_KEYS = {
  悠闲: 'prefs.pace.relaxed',
  适中: 'prefs.pace.moderate',
  紧凑: 'prefs.pace.packed',
}

/** 全部偏好值 -> i18n key 的合并索引。 */
export const PREFERENCE_LABEL_KEYS = {
  ...ATTRACTION_PREFERENCE_KEYS,
  ...FOOD_PREFERENCE_KEYS,
  ...BUDGET_KEYS,
  ...TRAVEL_PACE_KEYS,
}

/**
 * 偏好值 -> 当前语言的显示文案。
 *
 * 查不到映射时原样返回(避免把值吃成空字符串);返回值只用于渲染,
 * 调用方 emit / 落库时必须继续用原始值 `value`。
 */
export function preferenceLabel(value, t) {
  const raw = String(value ?? '')
  const key = PREFERENCE_LABEL_KEYS[raw]

  if (!key) {
    return raw
  }

  const label = t(key)

  return label && label !== key ? label : raw
}
