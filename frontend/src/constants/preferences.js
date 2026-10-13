/**
 * 偏好选项的唯一来源。
 *
 * 所有 Vue 文件都从这里取值,不允许把选项再抄一遍 ——
 * 否则 v0.2 想加一个标签就要满仓库搜索。
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
