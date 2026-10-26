import { getCurrentLocale } from '../i18n'
import { http } from './http'

/**
 * Chat 接口(§22)。
 *
 * v0.3 核心版本使用普通 HTTP Request/Response,不做流式输出。
 *
 * v0.3.1:发送时带上请求 locale(契约 §1:body 的 `locale` 优先于
 * `Accept-Language`)。它只影响**本次新生成**的 assistant 回答,
 * 绝不改写已保存的历史消息内容。
 */

/** §22.1 某个会话的历史消息;后端会先校验会话归属,历史文本原样返回。 */
export function getMessages(conversationId) {
  return http
    .get(`/conversations/${encodeURIComponent(String(conversationId ?? ''))}/messages`, {
      params: { locale: getCurrentLocale() },
    })
    .then((response) => response.data)
}

/**
 * §22.2 发送一条用户消息。
 *
 * 返回 { user_message, assistant_message, activities };
 * Agent 失败时后端返回可重试错误,前端不会伪造 assistant 消息。
 *
 * 注意:后端要跑完整的 Tool Calling 主循环(最多 AGENT_MAX_TOOL_ROUNDS 轮),
 * 多工具问题实测可达 30 秒以上,远超 http.js 默认的 15 秒。
 * 必须单独放宽超时,否则长回答会被前端自己掐断成"网络连接失败"。
 */
export function sendMessage(conversationId, content) {
  return http
    .post(
      `/conversations/${encodeURIComponent(String(conversationId ?? ''))}/messages`,
      { content: String(content ?? ''), locale: getCurrentLocale() },
      { timeout: 120000 },
    )
    .then((response) => response.data)
}
