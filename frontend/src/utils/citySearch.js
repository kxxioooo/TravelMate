import { MATCH_RANK, matchCityAliases, normalizeSearchText, rankCityResults } from './localeSearch'

/**
 * 纯前端城市搜索(v0.2 起本地匹配,不访问高德)。
 *
 * v0.3.1 起把"归一化 / 别名匹配 / 排序"下沉到 `utils/localeSearch.js`:
 * 中文名、中文片段、拼音、拼音首字母、英文名、英文别名都能命中,
 * 大小写与撇号不敏感(`xian` ≡ `xi'an`),排序固定为 精确 > 前缀 > 包含。
 *
 * 这里保留原有的三个函数名,调用方不需要改协议;命中的对象仍然只有
 * `city_name`(中文)+ `adcode`,展示名由 i18nDisplay 单独格式化。
 */

/** 统一关键词:去重音 / 撇号 / 多余空白 + 转小写。 */
export function normalizeKeyword(value) {
  return normalizeSearchText(value)
}

/** 城市名 / 省份 / 拼音 / 首字母 / 英文名 / 英文别名 任一命中即算匹配。 */
export function cityMatchesKeyword(city, keyword) {
  return matchCityAliases(city, keyword) > MATCH_RANK.NONE
}

/**
 * 返回最多 limit 个候选城市(精确 > 前缀 > 包含,同档保持索引顺序)。
 *
 * 空关键词返回空数组 —— Recent Searches 由调用方按需拼接。
 */
export function searchCities(cities, keyword, limit = 10) {
  return rankCityResults(cities, keyword, limit)
}
