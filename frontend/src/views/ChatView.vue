<template>
  <div class="shell">
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="side-head">
        <div class="logo">柳</div>
        <div class="brand-text">
          <strong>柳州文旅智能体</strong>
          <span>AI 旅行搭子</span>
        </div>
      </div>

      <button class="new-chat" @click="newChat">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14" stroke-linecap="round" />
        </svg>
        新对话
      </button>

      <button v-if="auth.user?.is_admin" class="admin-entry" @click="router.push('/admin')">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.55-1 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34h.01a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55h.01a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.01a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1z" />
        </svg>
        知识库管理
      </button>

      <p class="side-label">历史对话</p>

      <nav class="sessions">
        <p v-if="sessions.length === 0" class="empty-tip">还没有对话，先问一句试试</p>
        <button
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === currentId }"
          @click="openSession(s.id)"
        >
          <span class="dot"></span>
          <span class="title">{{ s.title }}</span>
          <span class="del" title="删除会话" @click.stop="removeSession(s)">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
        </button>
      </nav>

      <div class="side-user">
        <div class="user-avatar">{{ initial }}</div>
        <div class="user-meta">
          <strong>{{ auth.user?.username }}</strong>
          <span>已登录</span>
        </div>
        <button class="logout" title="退出登录" @click="doLogout">
          <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
    </aside>

    <div v-if="sidebarOpen" class="mask" @click="sidebarOpen = false"></div>

    <main class="main">
      <header class="topbar">
        <button class="menu" @click="sidebarOpen = !sidebarOpen" aria-label="菜单">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round" />
          </svg>
        </button>
        <div class="top-title">
          <h1>{{ currentTitle }}</h1>
          <span class="status"><i></i> 智能体在线</span>
        </div>
      </header>

      <section ref="scroller" class="messages">
        <div v-if="messages.length === 0" class="hero">
          <p class="eyebrow">LIUZHOU TRAVEL AGENT</p>
          <h2>今天想在柳州怎么玩？</h2>
          <p class="hero-sub">景点、螺蛳粉、两日游路线，或者只是聊聊天气，都可以。</p>
          <div class="chips">
            <button v-for="c in suggestions" :key="c" @click="send(c)">{{ c }}</button>
          </div>
        </div>

        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="msg-avatar">{{ m.role === 'user' ? initial : '柳' }}</div>
          <div class="bubble-wrap">
            <details v-if="m.process" class="process">
              <summary>思考过程<span v-if="m.streaming && !m.content" class="thinking-live"> · 思考中…</span></summary>
              <div class="process-body">{{ m.process }}</div>
            </details>
            <div class="bubble">
              <!-- 用户上传的文件列表 -->
              <div v-if="m.uploadedFiles && m.uploadedFiles.length" class="msg-files">
                <div
                  v-for="(f, fi) in m.uploadedFiles"
                  :key="fi"
                  class="msg-file"
                  :class="{ image: f.isImage }"
                >
                  <img
                    v-if="f.isImage && f.persistUrl"
                    :src="f.persistUrl"
                    :alt="f.name"
                  />
                  <div v-else class="doc-thumb">
                    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke-linecap="round" stroke-linejoin="round" />
                      <polyline points="14 2 14 8 20 8" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                  </div>
                  <div class="msg-file-meta">
                    <strong>{{ f.name }}</strong>
                    <span>{{ f.fileType }}</span>
                  </div>
                </div>
              </div>
              <div v-if="m.role === 'assistant'" class="md" v-html="renderMarkdown(m.content)"></div>
              <p v-else class="plain">{{ m.content }}</p>
              <span v-if="m.streaming" class="caret"></span>
            </div>
          </div>
        </div>
      </section>

      <footer class="composer">
        <div v-if="pendingFiles.length" class="file-strip">
          <div
            v-for="(f, idx) in pendingFiles"
            :key="idx"
            class="file-chip"
            :class="{ image: f.isImage, uploading: f.uploading }"
          >
            <div class="chip-thumb">
              <img v-if="f.isImage && f.localUrl" :src="f.localUrl" alt="" />
              <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke-linecap="round" stroke-linejoin="round" />
                <polyline points="14 2 14 8 20 8" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <span v-if="f.uploading" class="chip-spinner"></span>
            </div>
            <div class="chip-meta">
              <span class="chip-name">{{ f.name }}</span>
              <span class="chip-type">{{ f.uploading ? '上传中…' : (f.file_type || '已解析') }}</span>
            </div>
            <button v-if="!f.uploading" class="chip-del" @click="removePendingFile(idx)" title="移除">×</button>
          </div>
        </div>

        <div class="composer-box">
          <input
            ref="fileInput"
            type="file"
            multiple
            hidden
            accept=".txt,.md,.pdf,.docx,.jpg,.jpeg,.png,.webp,.gif,.bmp"
            @change="onPickFiles"
          />
          <button class="attach" type="button" @click="$refs.fileInput.click()" title="上传文件或图片" aria-label="上传文件">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <textarea
            ref="textarea"
            v-model="input"
            rows="1"
            :placeholder="pendingFiles.length ? `已选 ${pendingFiles.length} 个文件，可选输入问题…` : '问问柳州怎么玩、螺蛳粉哪家强…'"
            @keydown.enter.exact.prevent="send()"
            @input="autoGrow"
            @dragover.prevent
            @drop.prevent="onDropFiles"
          ></textarea>
          <button class="send" :disabled="sending || (!input.trim() && !pendingFiles.length)" @click="send()" aria-label="发送">
            <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 12h15M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </div>
        <p class="footnote">Enter 发送 · Shift + Enter 换行 · 支持 PDF / Word / TXT / 图片（拖拽也可上传）</p>
      </footer>

      <transition name="fade">
        <div v-if="toast" class="toast">{{ toast }}</div>
      </transition>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { sessionApi, streamChat, uploadFile } from '../api'
import { auth, logout } from '../store/auth'
import { renderMarkdown } from '../utils/markdown'

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']

function isImageName(name) {
  const lower = (name || '').toLowerCase()
  return IMAGE_EXTS.some((e) => lower.endsWith(e))
}

/**
 * 把任何来源的 uploadedFiles 统一成前端驼形命名:
 * - 后端 DB 返回: 蛇形 is_image / file_type / relative_path
 * - 前端 pendingFiles: 驼形 isImage / persistUrl
 * 统一后: { name, fileType, isImage, persistUrl }
 */
function normalizeFiles(list) {
  if (!list || !list.length) return list
  return list.map((f) => {
    const isImage = f.isImage ?? f.is_image ?? isImageName(f.name)
    const persistUrl = f.persistUrl || (f.relative_path ? `/files/${f.relative_path}` : null)
    return {
      name: f.name,
      fileType: f.file_type ?? f.fileType,
      isImage,
      persistUrl,
    }
  })
}

const router = useRouter()

const sessions = ref([])
const currentId = ref(null)
const messages = ref([])
const input = ref('')
const sending = ref(false)
const toast = ref('')
const sidebarOpen = ref(false)
const scroller = ref(null)
const textarea = ref(null)
const fileInput = ref(null)

// 待发送的文件列表: 已上传到后端解析, 等用户点发送时一并提交
const pendingFiles = ref([])

let toastTimer = null

const suggestions = [
  '柳州有哪些必去景点？',
  '推荐几家本地人常去的螺蛳粉店',
  '帮我规划柳州两日游',
  '柳州今天天气怎么样？',
]

const initial = computed(() => (auth.user?.username || '?').slice(0, 1).toUpperCase())
const currentTitle = computed(
  () => sessions.value.find((s) => s.id === currentId.value)?.title || '新对话'
)

function showToast(message) {
  toast.value = message
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2600)
}

function handleUnauthorized() {
  showToast('登录已过期，请重新登录')
  router.replace({ name: 'login' })
}

async function refreshSessions() {
  try {
    sessions.value = await sessionApi.list()
  } catch (e) {
    if (e.status === 401) handleUnauthorized()
  }
}

async function openSession(id) {
  if (sending.value) return
  currentId.value = id
  sidebarOpen.value = false
  try {
    const data = await sessionApi.messages(id)
    messages.value = data.map((m) => ({
      ...m,
      process: m.process || '',
      uploadedFiles: normalizeFiles(m.uploadedFiles),
    }))
    scrollToBottom()
  } catch (e) {
    if (e.status === 401) handleUnauthorized()
    else showToast(e.message)
  }
}

function newChat() {
  currentId.value = null
  messages.value = []
  input.value = ''
  pendingFiles.value = []
  sidebarOpen.value = false
  nextTick(() => {
    if (textarea.value) {
      textarea.value.style.height = 'auto'
      textarea.value.focus()
    }
  })
}

// ============ 文件处理 ============

function removePendingFile(idx) {
  pendingFiles.value.splice(idx, 1)
}

async function _uploadOne(file) {
  // 上传成功前用 blob URL 做即时预览 (上传完成后替换为后端持久化 URL)
  const localUrl = isImageName(file.name) ? URL.createObjectURL(file) : null
  const placeholder = {
    name: file.name,
    isImage: isImageName(file.name),
    localUrl,                // blob 临时 URL (仅上传瞬间用)
    persistUrl: null,        // 后端持久化 URL (上传成功后赋值, 刷新后仍可用)
    uploading: true,
  }
  pendingFiles.value.push(placeholder)
  const placeIdx = pendingFiles.value.length - 1

  try {
    const res = await uploadFile(file)
    pendingFiles.value[placeIdx] = {
      name: res.name,
      file_type: res.file_type,
      size: res.size,
      isImage: res.is_image ?? placeholder.isImage,
      localUrl,
      persistUrl: res.relative_path ? `/files/${res.relative_path}` : null,
      relative_path: res.relative_path,
      preview: res.preview,
      full_content: res.full_content,
      uploading: false,
    }
  } catch (e) {
    showToast(e.message || `上传失败: ${file.name}`)
    pendingFiles.value.splice(placeIdx, 1)
    if (localUrl) URL.revokeObjectURL(localUrl)
  }
}

function onPickFiles(e) {
  const files = Array.from(e.target.files || [])
  files.forEach(_uploadOne)
  // 清空 input, 让用户能连续选择同一个文件
  e.target.value = ''
}

function onDropFiles(e) {
  const files = Array.from(e.dataTransfer?.files || [])
  files.forEach(_uploadOne)
}

async function removeSession(session) {
  if (!window.confirm(`删除会话「${session.title}」？删除后不可恢复。`)) return
  try {
    await sessionApi.remove(session.id)
    sessions.value = sessions.value.filter((s) => s.id !== session.id)
    if (currentId.value === session.id) newChat()
  } catch (e) {
    if (e.status === 401) handleUnauthorized()
    else showToast(e.message)
  }
}

async function send(text) {
  const query = (typeof text === 'string' ? text : input.value).trim()
  const filesReady = pendingFiles.value.filter((f) => !f.uploading)
  const uploading = pendingFiles.value.some((f) => f.uploading)
  if (!query && filesReady.length === 0) return
  if (uploading) {
    showToast('文件还在上传中，请稍等')
    return
  }

  input.value = ''
  nextTick(resetTextarea)

  // 构建给后端的 uploaded_files 参数 (带 relative_path, 供后端落库持久化)
  const uploadedPayload = filesReady.map((f) => ({
    name: f.name,
    file_type: f.file_type,
    is_image: f.isImage,
    relative_path: f.relative_path,
    full_content: f.full_content,
  }))

  // 用户消息里展示的文件 (normalizeFiles 统一命名, 刷新后后端返回的数据也能无缝展示)
  const displayFiles = normalizeFiles(filesReady.map((f) => ({
    name: f.name,
    file_type: f.file_type,
    is_image: f.isImage,
    isImage: f.isImage,
    relative_path: f.relative_path,
    persistUrl: f.persistUrl,
  })))

  messages.value.push({
    role: 'user',
    content: query || '（查看上传的文件）',
    uploadedFiles: displayFiles,
  })
  messages.value.push({ role: 'assistant', content: '', process: '', streaming: true })
  const target = messages.value[messages.value.length - 1]

  // 清空 pendingFiles, 但保留 localUrl 让用户消息能继续展示图片
  pendingFiles.value = []

  sending.value = true
  scrollToBottom()

  let raw = ''

  try {
    await streamChat({
      query,
      sessionId: currentId.value,
      uploadedFiles: uploadedPayload,
      onEvent(event, data) {
        if (event === 'session') {
          currentId.value = data.session_id
        } else if (event === 'chunk') {
          // kind: answer=最终回答正文 / thinking=思考过程 / demote=误发进回答的思考收回
          const kind = data.kind || 'answer'
          if (kind === 'thinking') {
            target.process = (target.process || '') + data.text
          } else if (kind === 'demote') {
            target.process = (target.process || '') + data.text
            target.content = ''
            raw = ''
          } else {
            target.content = (target.content || '') + data.text
            raw += data.text
          }
          scrollToBottom()
        } else if (event === 'error') {
          showToast(data.message || '智能体执行出错')
        } else if (event === 'end') {
          const answer = data.answer || ''
          target.content = answer || raw
          // 后端下发的权威思考过程, 覆盖前端累积值, 避免流式期间的偏差
          if (data.process !== undefined) target.process = data.process
          target.streaming = false
          scrollToBottom()
        }
      },
    })

    target.streaming = false
    if (!target.content) target.content = '（服务暂时不可用，请稍后重试）'
    await refreshSessions()
  } catch (e) {
    target.streaming = false
    if (e.status === 401) {
      handleUnauthorized()
      return
    }
    showToast(e.message || '发送失败，请稍后重试')
    if (!target.content) {
      messages.value = messages.value.filter((m) => m !== target)
    }
  } finally {
    sending.value = false
  }
}

function resetTextarea() {
  if (textarea.value) textarea.value.style.height = 'auto'
}

function autoGrow(event) {
  const el = event.target
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 168)}px`
}

function scrollToBottom() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}

async function doLogout() {
  await logout()
  router.replace({ name: 'login' })
}

onMounted(async () => {
  await refreshSessions()
  if (sessions.value.length > 0) {
    await openSession(sessions.value[0].id)
  }
})
</script>

<style scoped>
.shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--bg);
}

/* ============ 侧边栏 ============ */
.sidebar {
  width: 272px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 22px 16px 16px;
  color: #e7f5f0;
  background: linear-gradient(180deg, #08312b 0%, #0a4b41 58%, #0c5a4d 100%);
}

.side-head {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 6px;
  margin-bottom: 22px;
}

.logo {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  font-weight: 700;
  font-size: 19px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.brand-text strong {
  font-size: 14.5px;
  letter-spacing: 0.5px;
}

.brand-text span {
  font-size: 11px;
  color: rgba(231, 245, 240, 0.5);
  letter-spacing: 1.5px;
}

.new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 11px 0;
  border-radius: 11px;
  font-size: 14px;
  font-weight: 600;
  color: #08312b;
  background: linear-gradient(120deg, #9be9d8, #5ed3bb);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
  transition: transform 0.16s ease, filter 0.16s ease;
}

.new-chat:hover {
  transform: translateY(-1px);
  filter: brightness(1.04);
}

.admin-entry {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  margin-top: 8px;
  padding: 10px 0;
  border-radius: 11px;
  font-size: 13.5px;
  font-weight: 600;
  color: rgba(231, 245, 240, 0.85);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
  transition: background 0.16s ease, color 0.16s ease;
}

.admin-entry:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

.side-label {
  margin: 24px 8px 10px;
  font-size: 11px;
  letter-spacing: 2px;
  color: rgba(231, 245, 240, 0.42);
}

.sessions {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin: 0 -4px;
  padding: 0 4px;
}

.sessions::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.14);
}

.empty-tip {
  margin: 8px 8px;
  font-size: 12.5px;
  color: rgba(231, 245, 240, 0.42);
  line-height: 1.7;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 10px 10px;
  border-radius: 10px;
  text-align: left;
  font-size: 13.5px;
  color: rgba(231, 245, 240, 0.78);
  transition: background 0.16s ease, color 0.16s ease;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.session-item.active {
  background: rgba(155, 233, 216, 0.16);
  color: #fff;
}

.dot {
  width: 6px;
  height: 6px;
  flex-shrink: 0;
  border-radius: 50%;
  background: rgba(155, 233, 216, 0.5);
}

.session-item.active .dot {
  background: #5ed3bb;
  box-shadow: 0 0 0 3px rgba(94, 211, 187, 0.2);
}

.title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.del {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border-radius: 7px;
  color: rgba(231, 245, 240, 0.45);
  opacity: 0;
  transition: all 0.15s ease;
}

.session-item:hover .del {
  opacity: 1;
}

.del:hover {
  background: rgba(228, 106, 138, 0.22);
  color: #ffb9ca;
}

.side-user {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 10px 4px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.user-avatar {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 700;
  color: #08312b;
  background: linear-gradient(135deg, #9be9d8, #4cc9ae);
}

.user-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  line-height: 1.4;
  overflow: hidden;
}

.user-meta strong {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-meta span {
  font-size: 11px;
  color: rgba(231, 245, 240, 0.45);
}

.logout {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  color: rgba(231, 245, 240, 0.6);
  transition: all 0.15s ease;
}

.logout:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

/* ============ 主区域 ============ */
.main {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: radial-gradient(circle at 88% -10%, #eaf6f2 0%, #f7faf8 42%, #ffffff 100%);
}

.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 26px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
}

.menu {
  display: none;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 9px;
  color: var(--teal-800);
}

.menu:hover {
  background: var(--teal-100);
}

.top-title {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.top-title h1 {
  margin: 0;
  font-size: 15.5px;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--muted);
  flex-shrink: 0;
}

.status i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #21b08f;
  box-shadow: 0 0 0 3px rgba(33, 176, 143, 0.16);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 30px 26px 18px;
  scroll-behavior: smooth;
}

.hero {
  max-width: 720px;
  margin: 8vh auto 0;
  text-align: center;
  animation: rise 0.45s ease both;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
}

.eyebrow {
  margin: 0 0 14px;
  font-size: 11px;
  letter-spacing: 3.5px;
  color: var(--teal-600);
  opacity: 0.7;
}

.hero h2 {
  margin: 0 0 12px;
  font-size: clamp(24px, 3vw, 32px);
  letter-spacing: 0.5px;
}

.hero-sub {
  margin: 0 0 26px;
  font-size: 14px;
  color: var(--muted);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.chips button {
  padding: 10px 16px;
  font-size: 13px;
  color: #33564d;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 999px;
  box-shadow: var(--shadow-sm);
  transition: all 0.16s ease;
}

.chips button:hover {
  color: var(--teal-800);
  border-color: rgba(18, 144, 124, 0.4);
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(14, 124, 107, 0.12);
}

.msg {
  display: flex;
  gap: 12px;
  max-width: 860px;
  margin: 0 auto 22px;
  animation: rise 0.28s ease both;
}

.msg.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  margin-top: 2px;
  border-radius: 11px;
  font-size: 14px;
  font-weight: 700;
}

.msg.assistant .msg-avatar {
  color: #fff;
  background: linear-gradient(135deg, var(--teal-700), var(--teal-600));
  box-shadow: 0 6px 14px rgba(14, 124, 107, 0.24);
}

.msg.user .msg-avatar {
  color: #08312b;
  background: linear-gradient(135deg, #ffe0e8, #f7c3d1);
}

.bubble-wrap {
  max-width: min(78%, 680px);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.msg.user .bubble-wrap {
  align-items: flex-end;
}

.bubble {
  padding: 13px 17px;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.75;
  box-shadow: var(--shadow-sm);
}

.msg.assistant .bubble {
  background: #fff;
  border: 1px solid var(--line);
  border-top-left-radius: 6px;
}

.msg.user .bubble {
  color: #fff;
  background: linear-gradient(135deg, #0f8875, #0b6a5b);
  border-top-right-radius: 6px;
  box-shadow: 0 8px 18px rgba(11, 106, 91, 0.22);
}

.plain {
  margin: 0;
  white-space: pre-wrap;
}

.msg-files {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.msg-file {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 10px;
  min-width: 0;
  max-width: 220px;
}

.msg-file.image {
  padding: 4px;
  flex-direction: column;
  align-items: stretch;
  max-width: 160px;
}

.msg-file img {
  max-width: 100%;
  max-height: 120px;
  border-radius: 7px;
  object-fit: cover;
  display: block;
}

.doc-thumb {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 7px;
  color: #fff;
  background: linear-gradient(135deg, rgba(255,255,255,0.25), rgba(255,255,255,0.1));
}

.msg-file-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.3;
  color: #fff;
}

.msg-file-meta strong {
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.msg-file-meta span {
  font-size: 10.5px;
  opacity: 0.75;
}

.process {
  font-size: 12.5px;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.7);
  border: 1px dashed #d5e3de;
  border-radius: 10px;
  padding: 8px 12px;
}

.process summary {
  cursor: pointer;
  user-select: none;
  font-weight: 600;
  color: #5c7a72;
}

.thinking-live {
  font-weight: 400;
  color: #12a08b;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.45; }
  50% { opacity: 1; }
}

.process-body {
  margin-top: 8px;
  white-space: pre-wrap;
  line-height: 1.7;
  max-height: 220px;
  overflow-y: auto;
  color: #6b7d78;
}

/* ============ 输入区 ============ */
.composer {
  padding: 12px 26px 18px;
}

.file-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-width: 860px;
  margin: 0 auto 8px;
}

.file-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px 6px 6px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 10px;
  min-width: 0;
  max-width: 260px;
  box-shadow: var(--shadow-sm);
  animation: rise 0.2s ease both;
}

.file-chip.uploading {
  opacity: 0.7;
}

.chip-thumb {
  position: relative;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 7px;
  color: #0f8875;
  background: linear-gradient(135deg, #e9f6f2, #cbebe1);
  overflow: hidden;
}

.chip-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chip-spinner {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  border: 2px solid transparent;
  border-top-color: #0f8875;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.chip-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.chip-name {
  font-size: 12.5px;
  font-weight: 600;
  color: #08312b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-type {
  font-size: 11px;
  color: #9aaba5;
}

.chip-del {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: #9aaba5;
  font-size: 14px;
  line-height: 1;
  transition: all 0.15s ease;
}

.chip-del:hover {
  color: #e85a7a;
  background: #fde7ee;
}

.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  max-width: 860px;
  margin: 0 auto;
  padding: 10px 10px 10px 14px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 10px 30px rgba(16, 50, 44, 0.08);
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.composer-box:focus-within {
  border-color: rgba(18, 144, 124, 0.5);
  box-shadow: 0 10px 34px rgba(14, 124, 107, 0.14);
}

.attach {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 10px;
  color: #5c7a72;
  transition: all 0.15s ease;
}

.attach:hover {
  color: var(--teal-800);
  background: #e9f6f2;
}

.composer-box textarea {
  flex: 1;
  resize: none;
  border: none;
  outline: none;
  padding: 8px 0;
  max-height: 168px;
  font-size: 14.5px;
  line-height: 1.65;
  background: transparent;
}

.composer-box textarea::placeholder {
  color: #9aaba5;
}

.send {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(135deg, var(--teal-700), var(--teal-600));
  box-shadow: 0 8px 16px rgba(14, 124, 107, 0.26);
  transition: all 0.16s ease;
}

.send:hover:not(:disabled) {
  transform: translateY(-1px);
}

.send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  box-shadow: none;
}

.footnote {
  max-width: 860px;
  margin: 9px auto 0;
  text-align: center;
  font-size: 11px;
  color: #9aaba5;
}

/* ============ 提示 ============ */
.toast {
  position: absolute;
  left: 50%;
  bottom: 108px;
  transform: translateX(-50%);
  padding: 10px 18px;
  font-size: 13px;
  color: #fff;
  background: rgba(20, 33, 30, 0.9);
  border-radius: 10px;
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(6px);
  white-space: nowrap;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.22s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.mask {
  display: none;
}

/* ============ 响应式 ============ */
@media (max-width: 860px) {
  .sidebar {
    position: fixed;
    z-index: 30;
    top: 0;
    bottom: 0;
    left: 0;
    transform: translateX(-100%);
    transition: transform 0.24s ease;
    box-shadow: 0 0 40px rgba(0, 0, 0, 0.28);
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .mask {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 20;
    background: rgba(8, 49, 43, 0.42);
    backdrop-filter: blur(2px);
  }

  .menu {
    display: grid;
  }

  .messages {
    padding: 22px 14px 12px;
  }

  .composer {
    padding: 10px 12px 14px;
  }

  .bubble-wrap {
    max-width: 86%;
  }

  .hero {
    margin-top: 5vh;
  }
}
</style>
