import cityIndex from '../data/cities.json'

/**
 * 多语言城市索引辅助检索(v0.3.1,跨端契约 §7)。
 *
 * 设计要点:
 *   1. 检索与展示严格分离 —— 检索命中的对象仍然只有 `city_name`(中文)+
 *      `adcode`,`displayBilingualName()` 之类的展示函数不会回流到请求参数;
 *   2. 大小写、撇号、空格不敏感(`xian` ≡ `xi'an`),中文片段、全拼、首字母、
 *      英文名、英文别名都能命中;
 *   3. `rankCityResults()` 固定排序:精确 > 前缀 > 包含,同档保持原始顺序,
 *      避免"每敲一个字候选顺序乱跳"。
 */

/** 匹配强度:数值越大越靠前。 */
export const MATCH_RANK = Object.freeze({
  NONE: 0,
  CONTAINS: 1,
  PREFIX: 2,
  EXACT: 3,
})

/**
 * 统一检索文本:去重音、转小写、去掉撇号类字符、压缩空白。
 *
 * 撇号不参与比较是契约要求:`xian` 与 `xi'an` 必须能定位到同一个城市。
 */
export function normalizeSearchText(value) {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[\u2018\u2019\u02bc'`´]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** 去掉全部空白后的检索文本,用于兼容 `hot pot` / `hotpot` 这类写法。 */
export function compactSearchText(value) {
  return normalizeSearchText(value).replace(/\s+/g, '')
}

/** 一个城市参与检索的全部字段(中文名、省份、拼音、首字母、英文名、英文别名)。 */
export function citySearchFields(city) {
  if (!city || typeof city !== 'object') {
    return []
  }

  const aliases = Array.isArray(city.aliases_en) ? city.aliases_en : []

  return [
    city.city_name,
    city.province,
    city.pinyin,
    city.pinyin_initials,
    city.city_name_en,
    city.province_en,
    ...aliases,
  ]
}

/** 单个字段的匹配强度。 */
function rankField(value, target) {
  if (!value || !target) {
    return MATCH_RANK.NONE
  }

  if (value === target) {
    return MATCH_RANK.EXACT
  }

  if (value.startsWith(target)) {
    return MATCH_RANK.PREFIX
  }

  if (value.includes(target)) {
    return MATCH_RANK.CONTAINS
  }

  return MATCH_RANK.NONE
}

/**
 * 城市是否命中关键词,返回 0~3 的匹配强度(0 = 未命中)。
 *
 * 同时比较"保留空格"和"去掉空格"两种形态,因此 `xi an` / `xian` / `西安` 都能命中。
 */
export function matchCityAliases(city, keyword) {
  const target = normalizeSearchText(keyword)

  if (!target) {
    return MATCH_RANK.NONE
  }

  const compactTarget = compactSearchText(keyword)
  let best = MATCH_RANK.NONE

  for (const field of citySearchFields(city)) {
    const value = normalizeSearchText(field)
    if (!value) {
      continue
    }

    best = Math.max(best, rankField(value, target))

    const compactValue = compactSearchText(field)
    if (compactValue && compactTarget) {
      best = Math.max(best, rankField(compactValue, compactTarget))
    }

    if (best === MATCH_RANK.EXACT) {
      return best
    }
  }

  return best
}

/**
 * 按"精确 > 前缀 > 包含"排序后返回候选城市。
 *
 * 原始数组不被修改,同档候选保持 cities.json 里的顺序(直辖市排前)。
 */
export function rankCityResults(cities, keyword, limit = 10) {
  const source = Array.isArray(cities) ? cities : []

  if (!normalizeSearchText(keyword)) {
    return []
  }

  const ranked = source
    .map((city, index) => ({ city, index, rank: matchCityAliases(city, keyword) }))
    .filter((item) => item.rank > MATCH_RANK.NONE)
    .sort((left, right) => right.rank - left.rank || left.index - right.index)

  return ranked.slice(0, Math.max(0, limit)).map((item) => item.city)
}

/**
 * 按 adcode(优先)或中文名在静态城市索引里找到权威记录。
 *
 * 历史搜索 / Conversation 城市只存中文名 + adcode,英文名回到索引里 join,
 * 绝不在数据库里另存一份"英文城市"。
 */
export function findCityRecord(city) {
  if (!city || typeof city !== 'object') {
    return null
  }

  const adcode = city.adcode === null || city.adcode === undefined ? '' : String(city.adcode)

  if (adcode) {
    const byAdcode = cityIndex.find((item) => String(item.adcode) === adcode)
    if (byAdcode) {
      return byAdcode
    }
  }

  const name = normalizeSearchText(city.city_name)
  if (!name) {
    return null
  }

  return cityIndex.find((item) => normalizeSearchText(item.city_name) === name) ?? null
}

/** 取第一个非空文本值,用于"后端字段优先、静态索引兜底"。 */
function firstText(...values) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
  }

  return ''
}

/**
 * 把后端返回的城市对象补全成带英文名的展示对象。
 *
 * 后端 / 历史记录只保证中文名与 adcode;`city_name_en`、`province_en`、
 * `pinyin`、`aliases_en` 等展示字段从静态索引补齐。缺失时保持空字符串,
 * 由展示层决定降级方式(绝不伪造英文名)。
 */
export function enrichCity(city) {
  if (!city || typeof city !== 'object') {
    return null
  }

  const record = findCityRecord(city) ?? {}

  return {
    ...record,
    ...city,
    city_name: firstText(city.city_name, record.city_name),
    province: firstText(city.province, record.province),
    adcode: city.adcode === null || city.adcode === undefined ? (record.adcode ?? '') : city.adcode,
    city_name_en: firstText(city.city_name_en, record.city_name_en),
    province_en: firstText(city.province_en, record.province_en),
    pinyin: firstText(city.pinyin, record.pinyin),
    pinyin_initials: firstText(city.pinyin_initials, record.pinyin_initials),
    aliases_en: Array.isArray(city.aliases_en) && city.aliases_en.length
      ? city.aliases_en
      : Array.isArray(record.aliases_en)
        ? record.aliases_en
        : [],
  }
}
