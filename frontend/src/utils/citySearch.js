/**
 * 纯前端城市搜索。
 *
 * v0.1 完全本地匹配,不访问高德;v0.2 接入高德后这里的基础算法继续复用。
 */

/** 统一关键词:去首尾空格 + 转小写。 */
export function normalizeKeyword(value) {
  return String(value ?? '')
    .trim()
    .toLowerCase()
}

/** 城市名 / 省份 / 拼音 任一命中即算匹配(子串匹配,支持"杭"和"hang")。 */
export function cityMatchesKeyword(city, keyword) {
  const target = normalizeKeyword(keyword)
  if (!target) {
    return false
  }

  return [city.city_name, city.province, city.pinyin]
    .map((field) => normalizeKeyword(field))
    .some((field) => field.includes(target))
}

/** 返回最多 limit 个候选城市。 */
export function searchCities(cities, keyword, limit = 10) {
  if (!normalizeKeyword(keyword)) {
    return []
  }

  return cities.filter((city) => cityMatchesKeyword(city, keyword)).slice(0, limit)
}
