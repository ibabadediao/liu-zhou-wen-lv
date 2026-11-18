import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

/**
 * 将模型返回的 Markdown 渲染为安全 HTML
 * 必须经过 DOMPurify 消毒, 防止模型输出中的脚本注入
 */
export function renderMarkdown(text) {
  if (!text) return ''
  // 转义数字之间的 ~ (如温度区间 15~19), 防止 marked GFM 下标语法吞掉波浪号
  const escaped = text.replace(/(\d)~(\d)/g, '$1\\~$2')
  return DOMPurify.sanitize(marked.parse(escaped))
}
