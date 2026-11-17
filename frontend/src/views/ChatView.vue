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
              <summary>思考过程</summary>
              <div class="process-body">{{ m.process }}</div>
            </details>
            <div class="bubble">
              <div v-if="m.role === 'assistant'" class="md" v-html="renderMarkdown(m.content)"></div>
              <p v-else class="plain">{{ m.content }}</p>
              <span v-if="m.streaming" class="caret"></span>
            </div>
          </div>
        </div>
      </section>

      <footer class="composer">
        <div class="composer-box">
          <textarea
            ref="textarea"
            v-model="input"
            rows="1"
            placeholder="问问柳州怎么玩、螺蛳粉哪家强…"
            @keydown.enter.exact.prevent="send()"
            @input="autoGrow"
          ></textarea>
          <button class="send" :disabled="sending || !input.trim()" @click="send()" aria-label="发送">
            <svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 12h15M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </div>
        <p class="footnote">Enter 发送 · Shift + Enter 换行 · 会话仅自己可见</p>
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
import { sessionApi, streamChat } from '../api'
import { auth, logout } from '../store/auth'
import { renderMarkdown } from '../utils/markdown'

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
    messages.value = data.map((m) => ({ ...m, process: '' }))
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
  sidebarOpen.value = false
  nextTick(() => {
    if (textarea.value) {
      textarea.value.style.height = 'auto'
      textarea.value.focus()
    }
  })
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
  if (!query || sending.value) return

  input.value = ''
  nextTick(resetTextarea)

  messages.value.push({ role: 'user', content: query })
  messages.value.push({ role: 'assistant', content: '', process: '', streaming: true })
  const target = messages.value[messages.value.length - 1]

  sending.value = true
  scrollToBottom()

  let raw = ''

  try {
    await streamChat({
      query,
      sessionId: currentId.value,
      onEvent(event, data) {
        if (event === 'session') {
          currentId.value = data.session_id
        } else if (event === 'chunk') {
          raw += data.text
          target.content = raw
          scrollToBottom()
        } else if (event === 'error') {
          showToast(data.message || '智能体执行出错')
        } else if (event === 'end') {
          const answer = data.answer || ''
          const idx = answer ? raw.lastIndexOf(answer) : -1
          if (idx > 0) target.process = raw.slice(0, idx).trim()
          target.content = answer || raw
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

.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  max-width: 860px;
  margin: 0 auto;
  padding: 10px 10px 10px 18px;
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
