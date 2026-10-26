/**
 * 已审核的展示用术语映射(v0.3.1)。
 *
 * 这里只解决"把后端枚举 / 高德中文标签换成当前语言的 i18n key"这一件事,
 * 不做任何翻译调用、不编造英文名:
 *   - 天气:后端给 `weather_code` 就直接用;老响应只给中文文本时,用
 *     `WEATHER_TEXT_TO_CODE`(与跨端契约 §8 `weather_codes` 一致)兜底;
 *   - 穿衣:`clothing_advice_codes` 枚举;
 *   - 分类标签:高德中文标签 -> i18n key,未收录的标签保持原样(原始数据不算
 *     "未授权中文",但绝不臆造译名)。
 */

/** 天气枚举(跨端契约 §3),未收录的 code 一律落到 UNKNOWN。 */
export const WEATHER_CODES = Object.freeze([
  'SUNNY',
  'CLOUDY',
  'OVERCAST',
  'LIGHT_RAIN',
  'MODERATE_RAIN',
  'HEAVY_RAIN',
  'THUNDERSTORM',
  'SNOW',
  'SLEET',
  'FOG',
  'HAZE',
  'WINDY',
  'UNKNOWN',
])

/** 穿衣建议枚举(跨端契约 §3)。 */
export const CLOTHING_CODES = Object.freeze([
  'HEAVY_COAT',
  'COAT_SWEATER',
  'LIGHT_JACKET',
  'SHORT_SLEEVE',
  'LIGHT_BREATHABLE',
  'UMBRELLA',
  'UNKNOWN',
])

/**
 * 中文天气文本 -> 天气 code。
 *
 * 仅用于后端还没返回 `weather_code` 的过渡期,避免英文界面里残留中文天气。
 */
export const WEATHER_TEXT_TO_CODE = Object.freeze({
  晴: 'SUNNY',
  晴天: 'SUNNY',
  多云: 'CLOUDY',
  阴: 'OVERCAST',
  阴天: 'OVERCAST',
  小雨: 'LIGHT_RAIN',
  阵雨: 'LIGHT_RAIN',
  中雨: 'MODERATE_RAIN',
  大雨: 'HEAVY_RAIN',
  暴雨: 'HEAVY_RAIN',
  雷阵雨: 'THUNDERSTORM',
  雷雨: 'THUNDERSTORM',
  雪: 'SNOW',
  小雪: 'SNOW',
  中雪: 'SNOW',
  大雪: 'SNOW',
  雨夹雪: 'SLEET',
  雾: 'FOG',
  霾: 'HAZE',
  沙尘: 'HAZE',
  大风: 'WINDY',
})

/**
 * 高德中文风向 -> i18n key。
 *
 * 注意:高德实际返回的既可能是"北风/东北风"这种带"风"的写法,
 * 也可能是单字"北/东北"(实测 weatherInfo 的 winddirection 就是单字)。
 * 两种都要收录,另外把"微风/静风/无持续风向"一并归到 variable。
 */
export const WIND_DIRECTION_KEYS = Object.freeze({
  东风: 'weather.wind_east',
  东: 'weather.wind_east',
  西风: 'weather.wind_west',
  西: 'weather.wind_west',
  北风: 'weather.wind_north',
  北: 'weather.wind_north',
  南风: 'weather.wind_south',
  南: 'weather.wind_south',
  东北风: 'weather.wind_northeast',
  东北: 'weather.wind_northeast',
  西北风: 'weather.wind_northwest',
  西北: 'weather.wind_northwest',
  东南风: 'weather.wind_southeast',
  东南: 'weather.wind_southeast',
  西南风: 'weather.wind_southwest',
  西南: 'weather.wind_southwest',
  无持续风向: 'weather.wind_variable',
  微风: 'weather.wind_variable',
  静风: 'weather.wind_variable',
})

/** 高德分类标签 -> i18n key(仅收录已审核的常用标签)。 */
export const TAG_LABEL_KEYS = Object.freeze({
  风景名胜: 'attraction.tag.scenic_spot',
  公园广场: 'attraction.tag.park',
  寺庙道观: 'attraction.tag.temple',
  博物馆: 'attraction.tag.museum',
  旅游景点: 'attraction.tag.tourist_site',
  动物园: 'attraction.tag.zoo',
  植物园: 'attraction.tag.botanical_garden',
  纪念馆: 'attraction.tag.memorial',
  教堂: 'attraction.tag.church',
  城市广场: 'attraction.tag.city_square',
  特色街区: 'attraction.tag.featured_street',
  地标: 'attraction.tag.landmark',
  山: 'attraction.tag.mountain',
  湖泊: 'attraction.tag.lake',
  餐饮服务: 'restaurant.tag.restaurant',
  中餐厅: 'restaurant.tag.chinese',
  火锅店: 'restaurant.tag.hotpot',
  小吃快餐: 'restaurant.tag.snack',
})

/** 统一 code 形态:去空、转大写。 */
function normalizeCode(value) {
  return String(value ?? '').trim().toUpperCase()
}

/**
 * 解析天气 code:`weather_code` 优先,老响应退回中文文本映射,最后 UNKNOWN。
 *
 * 返回值一定是枚举里的值,调用方可以直接拼 `weather.<CODE>`。
 */
export function resolveWeatherCode(weather) {
  const code = normalizeCode(weather?.weather_code)

  if (code && WEATHER_CODES.includes(code)) {
    return code
  }

  const text = typeof weather?.weather === 'string' ? weather.weather.trim() : ''

  if (!text) {
    return 'UNKNOWN'
  }

  if (WEATHER_TEXT_TO_CODE[text]) {
    return WEATHER_TEXT_TO_CODE[text]
  }

  for (const [keyword, mapped] of Object.entries(WEATHER_TEXT_TO_CODE)) {
    if (text.includes(keyword)) {
      return mapped
    }
  }

  return 'UNKNOWN'
}

/** 天气展示文案:始终落在当前语言,不会把中文天气漏到英文界面。 */
export function resolveWeatherLabel(weather, t) {
  const code = resolveWeatherCode(weather)

  return t(`weather.${code}`)
}

/**
 * 穿衣建议展示文案数组。
 *
 * 后端没有 `clothing_advice_codes` 时返回空数组,由调用方退回原始
 * `clothing_advice` 文本(向后兼容降级,不猜测建议内容)。
 */
export function resolveClothingLabels(codes, t) {
  if (!Array.isArray(codes)) {
    return []
  }

  const labels = []

  for (const item of codes) {
    const code = normalizeCode(item)
    if (!CLOTHING_CODES.includes(code) || code === 'UNKNOWN') {
      continue
    }

    labels.push(t(`clothing.${code}`))
  }

  return labels
}

/** 单个分类标签的展示文案(英文模式下查已审核映射,查不到保持原始数据)。 */
export function resolveTagLabel(tag, t, locale) {  const text = String(tag ?? '').trim()

  if (!text) {
    return ''
  }

  if (locale !== 'en-US') {
    return text
  }

  const key = TAG_LABEL_KEYS[text]
  if (!key) {
    return text
  }

  const label = t(key)

  return label && label !== key ? label : text
}

/**
 * 风向展示文案。
 *
 * 高德给的是中文风向(`东风`),跨端契约没有风向 code,所以这里用已审核映射
 * 在英文模式翻成 `Easterly`;未收录的写法保持原值(数据原文,不臆造)。
 */
export function resolveWindDirectionLabel(direction, t, locale) {
  const text = String(direction ?? '').trim()

  if (!text || locale !== 'en-US') {
    return text
  }

  // 高德可能给"北"或"北风",两种写法都试一次
  const candidates = [text, text.replace(/风$/, ''), `${text.replace(/风$/, '')}风`]
  const key = candidates.map((item) => WIND_DIRECTION_KEYS[item]).find(Boolean)

  if (!key) {
    return text
  }

  const label = t(key)

  return label && label !== key ? label : text
}

/** 是否含中日韩汉字(用于判断一个标签/文案能否在英文模式下直接展示)。 */
function containsChinese(text) {
  return /[\u4e00-\u9fff]/.test(String(text ?? ''))
}

/**
 * 标签列表展示。
 *
 * 英文模式优先用后端给的 `tags_en`(契约 §2 的详情字段);没有英文标签时
 * 逐条查 `TAG_LABEL_KEYS`,仍未收录的保留高德原始标签。
 */
export function resolveLocalizedTags(tags, tagsEn, locale, t) {
  const zhTags = Array.isArray(tags)
    ? tags.filter((tag) => typeof tag === 'string' && tag.trim()).map((tag) => tag.trim())
    : []

  if (locale === 'en-US') {
    const enTags = Array.isArray(tagsEn) ? tagsEn : []

    const localized = zhTags.map((zh, index) => {
      const en = typeof enTags[index] === 'string' ? enTags[index].trim() : ''

      if (en && !containsChinese(en)) {
        return en
      }

      const fallback = resolveTagLabel(zh, t, 'en-US')

      // 标签属于"类别描述"而非专有名词(契约 §1.4):英文模式下拿不到英文就整条不显示,
      // 绝不把未翻译的中文标签漏进英文界面。
      return fallback && !containsChinese(fallback) ? fallback : ''
    })

    return localized.filter(Boolean)
  }

  return zhTags
}
