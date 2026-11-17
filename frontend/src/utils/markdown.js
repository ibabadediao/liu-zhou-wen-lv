import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

/**
 * 将模型返回的 Markdown 渲染为安全 HTML
 * 必须经过 DOMPurify 消毒, 防止模型输出中的脚本注入
 */
export function renderMarkdown(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text))
}
