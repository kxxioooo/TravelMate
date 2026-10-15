/**
 * Chat 相关的纯前端工具(§26)。
 *
 * 这里只做"展示层兜底":真正的消息与 Activity 都以后端返回为准,
 * 前端绝不自己编造任何一条 message / tool 调用。
 */

/** 本地临时消息的自增序号,保证同一次会话里的临时 id 不撞车。 */
let localMessageSeed = 0

/**
 * §26.1 生成一条只在 UI 里存在的临时 user message。
 *
 * 发送时先把它插进列表,后端返回后再用正式 user_message 替换,
 * 这样用户不会觉得"点了发送没反应"。
 */
export function buildLocalUserMessage(content) {
  localMessageSeed += 1

  return {
    id: `local-${Date.now()}-${localMessageSeed}`,
    role: 'user',
    content: String(content ?? ''),
    pending: true,
  }
}

/** Activity 允许的状态:other 值一律按 success 兜底,但不会凭空造工具。 */
const ACTIVITY_STATUSES = new Set(['success', 'running', 'error'])

/**
 * §26.2 过滤异常 Activity,并保证每项都有 type / status / text。
 *
 * text 为空的项直接丢弃 —— 前端只展示后端真实给到的活动文案,
 * 绝不展示 prompt、思维链或工具内部 payload(§34 / §43)。
 */
export function normalizeActivities(items) {
  if (!Array.isArray(items)) {
    return []
  }

  const result = []

  for (const item of items) {
    if (!item || typeof item !== 'object') {
      continue
    }

    const text = typeof item.text === 'string' ? item.text.trim() : ''
    if (!text) {
      continue
    }

    result.push({
      type: typeof item.type === 'string' && item.type ? item.type : 'agent',
      status: ACTIVITY_STATUSES.has(item.status) ? item.status : 'success',
      text,
    })
  }

  return result
}

/**
 * §26.3 Conversation 标题展示兜底。
 *
 * 后端 build_conversation_title() 仍是权威 title;这里只在标题为空
 * 或过长时保证 Drawer 里不会出现空行 / 撑破布局。
 */
export function fallbackConversationTitle(message) {
  const text = String(message ?? '')
    .replace(/\s+/g, ' ')
    .trim()

  if (!text) {
    return '新对话'
  }

  return text.length > 20 ? `${text.slice(0, 20)}…` : text
}
