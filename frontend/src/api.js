/**
 * 后端接口封装
 * 所有请求携带 credentials: 'include', 让浏览器自动带上 httpOnly Cookie
 * 401 统一抛出 status=401 的错误, 由上层跳转登录页
 */

async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    const err = new Error('未登录或登录已过期')
    err.status = 401
    throw err
  }

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || `请求失败(${res.status})`)
    err.status = res.status
    throw err
  }
  return data
}

export const authApi = {
  me: () => request('/auth/me'),
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: { username, password } }),
  register: (username, password) =>
    request('/auth/register', { method: 'POST', body: { username, password } }),
  logout: () => request('/auth/logout', { method: 'POST' }),
}

export const sessionApi = {
  list: () => request('/sessions'),
  messages: (id) => request(`/sessions/${id}/messages`),
  remove: (id) => request(`/sessions/${id}`, { method: 'DELETE' }),
}

/**
 * 文件上传: multipart/form-data, 后端保存 + 解析后返回预览和全文
 */
export async function uploadFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch('/upload', {
    method: 'POST',
    credentials: 'include',
    body: fd,
  })
  if (res.status === 401) {
    const err = new Error('未登录或登录已过期')
    err.status = 401
    throw err
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `上传失败(${res.status})`)
  }
  return data
}

/**
 * 流式对话: 用 fetch + ReadableStream 解析 SSE
 * (EventSource 不支持自定义请求体与 POST, 因此手写解析)
 */
export async function streamChat({ query, sessionId, uploadedFiles, onEvent, signal }) {
  const body = { query, session_id: sessionId }
  if (uploadedFiles && uploadedFiles.length) {
    body.uploaded_files = uploadedFiles
  }
  const res = await fetch('/chat', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (res.status === 401) {
    const err = new Error('未登录或登录已过期')
    err.status = 401
    throw err
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `请求失败(${res.status})`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)

      let event = 'message'
      let data = ''
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) continue

      try {
        onEvent(event, JSON.parse(data))
      } catch {
        // 单帧解析失败不影响后续帧
      }
    }
  }
}
