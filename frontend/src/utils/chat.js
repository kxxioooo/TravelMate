import { translate } from '../i18n'

/**
 * Chat 相关的纯前端工具。
 *
 * 这里只做"展示层兜底":真正的消息与 Activity 都以后端返回为准,
 * 前端绝不自己编造任何一条 message / tool 调用。
 *
 * v0.3.1:Activity 改为"机器可读 code + params"驱动(跨端契约 §4),
 * `text` 仅作向后兼容兜底;标题等固定文案改走 i18n。
 */

/** 本地临时消息的自增序号,保证同一次会话里的临时 id 不撞车。 */
let localMessageSeed = 0

/**
 * 生成一条只在 UI 里存在的临时 user message。
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
 * 过滤异常 Activity,并保证每项都有 type / status / code / params / text。
 *
 * - `code` + `params` 是 v0.3.1 的权威展示来源(后端原始中文 `text` 只兜底);
 * - 两者都空的项直接丢弃,绝不展示 prompt、思维链或工具内部 payload;
 * - `params` 里的值都是原始中文 / ID,本地化只发生在渲染时。
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
    const code = typeof item.code === 'string' ? item.code.trim() : ''

    if (!text && !code) {
      continue
    }

    result.push({
      type: typeof item.type === 'string' && item.type ? item.type : 'agent',
      status: ACTIVITY_STATUSES.has(item.status) ? item.status : 'success',
      code,
      params: item.params && typeof item.params === 'object' ? { ...item.params } : null,
      text,
    })
  }

  return result
}

/**
 * Conversation 标题展示兜底。
 *
 * 后端 build_conversation_title() 仍是权威 title;这里只在标题为空
 * 或过长时保证 Drawer 里不会出现空行 / 撑破布局。
 * 空标题用当前语言的"新对话",不再硬编码中文。
 */
export function fallbackConversationTitle(message) {
  const text = String(message ?? '')
    .replace(/\s+/g, ' ')
    .trim()

  if (!text) {
    return translate('conversation.untitled')
  }

  const title = text.length > 20 ? `${text.slice(0, 20)}…` : text

  return title
}
