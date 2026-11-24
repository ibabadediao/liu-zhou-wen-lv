<template>
  <div class="admin-shell">
    <header class="topbar">
      <button class="back" @click="router.push('/chat')">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        返回对话
      </button>
      <div class="top-title">
        <h1>管理后台</h1>
        <span class="count">{{ tab === 'kb' ? `${documents.length} 个文档` : `${users.length} 个用户` }}</span>
      </div>
      <div class="tabs">
        <button :class="{ active: tab === 'kb' }" @click="tab = 'kb'">知识库</button>
        <button :class="{ active: tab === 'users' }" @click="tab = 'users'">用户管理</button>
      </div>
    </header>

    <main class="content">
      <template v-if="tab === 'kb'">
        <section class="upload-card">
        <div class="upload-head">
          <div>
            <h2>新增文档</h2>
            <p>上传 txt / pdf，保存后自动切分并向量化入库，AI 回答即可检索到。</p>
          </div>
          <input
            ref="fileInput"
            type="file"
            hidden
            accept=".txt,.pdf"
            @change="onPickFile"
          />
          <button class="upload-btn" :disabled="uploading" @click="$refs.fileInput.click()">
            <span v-if="!uploading">选择文件上传</span>
            <span v-else class="mini-spinner"></span>
          </button>
        </div>
        <p v-if="picked" class="picked">已选择：{{ picked.name }}（{{ formatSize(picked.size) }}）</p>
      </section>

      <section class="list-card">
        <div class="list-head">
          <div>
            <h2>知识库文档</h2>
            <span class="hint">删除会同时移除源文件与向量数据</span>
          </div>
          <button
            class="batch-btn"
            :disabled="pendingCount === 0 || batchBusy"
            @click="ingestAllPending"
          >
            <span v-if="!batchBusy">批量入库{{ pendingCount ? `（${pendingCount}）` : '' }}</span>
            <span v-else class="mini-spinner dark"></span>
          </button>
        </div>

        <div v-if="loading" class="empty">加载中…</div>
        <div v-else-if="documents.length === 0" class="empty">知识库为空，先上传一个文档吧</div>

        <ul v-else class="doc-list">
          <li v-for="d in documents" :key="d.name" class="doc-item">
            <div class="doc-icon" :class="d.type">{{ d.type.toUpperCase() }}</div>
            <div class="doc-meta">
              <strong class="doc-name" :title="d.name">{{ d.name }}</strong>
              <span class="doc-sub">
                {{ formatSize(d.size) }}
                <template v-if="d.ingested"> · {{ d.chunks }} 个文本块</template>
                <template v-else> · 未入库</template>
              </span>
            </div>
            <span class="badge" :class="{ ok: d.ingested }">
              {{ d.ingested ? '已入库' : '未入库' }}
            </span>
            <button
              class="re"
              :disabled="busyName === d.name"
              :title="d.ingested ? '重新入库' : '入库'"
              @click="reingest(d)"
            >
              <span v-if="busyName === d.name" class="mini-spinner dark"></span>
              <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 11a8 8 0 1 0-2.3 6" stroke-linecap="round" />
                <path d="M20 5v6h-6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
            <button class="del" @click="removeDoc(d)" title="删除文档">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </li>
        </ul>
      </section>
      </template>

      <template v-else>
        <section class="upload-card">
          <div class="upload-head">
            <div>
              <h2>新建用户</h2>
              <p>用户名 3-32 位，密码 6-64 位；勾选管理员后该账号可进入本后台。</p>
            </div>
          </div>
          <form class="create-form" @submit.prevent="createUser">
            <input v-model.trim="newUser.username" placeholder="用户名" autocomplete="off" />
            <input
              v-model="newUser.password"
              type="password"
              placeholder="初始密码"
              autocomplete="new-password"
            />
            <label class="checkbox">
              <input v-model="newUser.isAdmin" type="checkbox" />
              管理员
            </label>
            <button class="upload-btn" type="submit" :disabled="creating">
              <span v-if="!creating">创建</span>
              <span v-else class="mini-spinner"></span>
            </button>
          </form>
        </section>

        <section class="list-card">
          <div class="list-head">
            <div>
              <h2>用户列表</h2>
              <span class="hint">删除用户会同时清空其全部会话记录</span>
            </div>
          </div>

          <div v-if="usersLoading" class="empty">加载中…</div>
          <div v-else-if="users.length === 0" class="empty">暂无用户</div>

          <ul v-else class="doc-list">
            <li v-for="u in users" :key="u.id" class="doc-item user-item">
              <div class="avatar">{{ u.username.slice(0, 1).toUpperCase() }}</div>
              <div class="doc-meta">
                <strong class="doc-name">
                  {{ u.username }}
                  <span v-if="u.id === currentUserId" class="me">（我）</span>
                </strong>
                <span class="doc-sub">注册于 {{ u.created_at }}</span>
              </div>
              <span class="badge" :class="{ ok: u.is_admin }">
                {{ u.is_admin ? '管理员' : '普通用户' }}
              </span>
              <button class="text-btn" @click="openHistory(u)">问答记录</button>
              <button class="text-btn" @click="resetPassword(u)">重置密码</button>
              <button
                class="text-btn"
                :disabled="u.id === currentUserId"
                @click="toggleAdmin(u)"
              >
                {{ u.is_admin ? '取消管理员' : '设为管理员' }}
              </button>
              <button
                class="del"
                :disabled="u.id === currentUserId"
                @click="removeUser(u)"
                title="删除用户"
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </button>
            </li>
          </ul>
        </section>
      </template>
    </main>

    <transition name="fade">
      <div v-if="historyUser" class="modal-mask" @click.self="closeHistory">
        <div class="modal">
          <header class="modal-head">
            <div>
              <h3>{{ historyUser.username }} 的问答记录</h3>
              <span class="modal-sub">
                {{ activeSession ? activeSession.title : `${sessions.length} 个会话` }}
              </span>
            </div>
            <button class="modal-close" @click="closeHistory" title="关闭">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
              </svg>
            </button>
          </header>

          <div class="modal-body">
            <template v-if="!activeSession">
              <div v-if="sessionsLoading" class="empty">加载中…</div>
              <div v-else-if="sessions.length === 0" class="empty">该用户还没有问答记录</div>
              <ul v-else class="session-list">
                <li v-for="s in sessions" :key="s.id" @click="openSession(s)">
                  <span class="session-title">{{ s.title }}</span>
                  <span class="session-time">{{ s.updated_at }}</span>
                </li>
              </ul>
            </template>

            <template v-else>
              <button class="text-btn back-link" @click="activeSession = null">← 返回会话列表</button>
              <div v-if="messagesLoading" class="empty">加载中…</div>
              <div v-else-if="messages.length === 0" class="empty">该会话没有消息</div>
              <div v-else class="msg-list">
                <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
                  <div class="msg-role">{{ m.role === 'user' ? '用户' : 'AI' }}</div>
                  <div class="msg-text">{{ m.content }}</div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </transition>

    <transition name="fade">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi, kbApi, uploadKbDocument, userApi } from '../api'

const router = useRouter()

const tab = ref('kb')

const documents = ref([])
const loading = ref(true)
const uploading = ref(false)
const picked = ref(null)
const toast = ref('')
const fileInput = ref(null)
const batchBusy = ref(false)
const busyName = ref('')

const users = ref([])
const usersLoading = ref(true)
const creating = ref(false)
const currentUserId = ref(null)
const newUser = ref({ username: '', password: '', isAdmin: false })

// 问答记录弹窗
const historyUser = ref(null)
const sessions = ref([])
const sessionsLoading = ref(false)
const activeSession = ref(null)
const messages = ref([])
const messagesLoading = ref(false)

// 未入库文档数量: 决定「批量入库」按钮是否可用
const pendingCount = computed(() => documents.value.filter((d) => !d.ingested).length)

let toastTimer = null

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function showToast(message) {
  toast.value = message
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 2600)
}

async function refresh() {
  try {
    documents.value = await kbApi.list()
  } catch (e) {
    if (e.status === 401) {
      router.replace({ name: 'login' })
      return
    }
    showToast(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function onPickFile(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  picked.value = file
  uploading.value = true
  try {
    const res = await uploadKbDocument(file)
    showToast(res.ingested ? `「${res.name}」已入库（${res.chunks} 个文本块）` : `「${res.name}」已保存`)
    picked.value = null
    await refresh()
  } catch (err) {
    if (err.status === 401) {
      router.replace({ name: 'login' })
      return
    }
    showToast(err.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function removeDoc(doc) {
  if (!window.confirm(`删除文档「${doc.name}」？删除后不可恢复。`)) return
  try {
    await kbApi.remove(doc.name)
    showToast('已删除')
    await refresh()
  } catch (e) {
    if (e.status === 401) {
      router.replace({ name: 'login' })
      return
    }
    showToast(e.message || '删除失败')
  }
}

async function reingest(doc) {
  busyName.value = doc.name
  try {
    const res = await kbApi.reingest(doc.name)
    showToast(res.ingested ? `「${res.name}」已入库（${res.chunks} 个文本块）` : `「${res.name}」内容为空，未入库`)
    await refresh()
  } catch (e) {
    if (e.status === 401) {
      router.replace({ name: 'login' })
      return
    }
    showToast(e.message || '入库失败')
  } finally {
    busyName.value = ''
  }
}

async function ingestAllPending() {
  batchBusy.value = true
  try {
    const res = await kbApi.ingestPending()
    showToast(res.count ? `已批量入库 ${res.count} 个文档` : '没有待入库的文档')
    await refresh()
  } catch (e) {
    if (e.status === 401) {
      router.replace({ name: 'login' })
      return
    }
    showToast(e.message || '批量入库失败')
  } finally {
    batchBusy.value = false
  }
}

// ============ 用户管理 ============

function isUnauthorized(e) {
  if (e.status !== 401) return false
  router.replace({ name: 'login' })
  return true
}

async function loadUsers() {
  try {
    users.value = await userApi.list()
  } catch (e) {
    if (isUnauthorized(e)) return
    showToast(e.message || '加载用户失败')
  } finally {
    usersLoading.value = false
  }
}

async function loadMe() {
  try {
    const res = await authApi.me()
    currentUserId.value = res.user.id
  } catch {
    // 401 由其他请求统一跳转登录页
  }
}

async function createUser() {
  const { username, password, isAdmin } = newUser.value
  if (!username || !password) {
    showToast('请填写用户名和密码')
    return
  }
  creating.value = true
  try {
    await userApi.create(username, password, isAdmin)
    showToast(`用户「${username}」已创建`)
    newUser.value = { username: '', password: '', isAdmin: false }
    await loadUsers()
  } catch (e) {
    if (isUnauthorized(e)) return
    showToast(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function resetPassword(u) {
  const password = window.prompt(`为「${u.username}」设置新密码（6-64 位）`)
  if (!password) return
  try {
    await userApi.resetPassword(u.id, password)
    showToast('密码已重置')
  } catch (e) {
    if (isUnauthorized(e)) return
    showToast(e.message || '重置失败')
  }
}

async function toggleAdmin(u) {
  const target = !u.is_admin
  try {
    await userApi.setAdmin(u.id, target)
    showToast(target ? '已设为管理员' : '已取消管理员')
    await loadUsers()
  } catch (e) {
    if (isUnauthorized(e)) return
    showToast(e.message || '操作失败')
  }
}

async function removeUser(u) {
  if (!window.confirm(`删除用户「${u.username}」？其全部会话记录会一并删除，且不可恢复。`)) return
  try {
    await userApi.remove(u.id)
    showToast('用户已删除')
    await loadUsers()
  } catch (e) {
    if (isUnauthorized(e)) return
    showToast(e.message || '删除失败')
  }
}

async function openHistory(u) {
  historyUser.value = u
  activeSession.value = null
  sessions.value = []
  sessionsLoading.value = true
  try {
    sessions.value = await userApi.sessions(u.id)
  } catch (e) {
    if (isUnauthorized(e)) {
      closeHistory()
      return
    }
    showToast(e.message || '加载会话失败')
  } finally {
    sessionsLoading.value = false
  }
}

function closeHistory() {
  historyUser.value = null
  activeSession.value = null
  sessions.value = []
  messages.value = []
}

async function openSession(s) {
  activeSession.value = s
  messages.value = []
  messagesLoading.value = true
  try {
    const res = await userApi.messages(s.id)
    messages.value = res.messages
  } catch (e) {
    if (isUnauthorized(e)) {
      closeHistory()
      return
    }
    showToast(e.message || '加载消息失败')
  } finally {
    messagesLoading.value = false
  }
}

onMounted(() => {
  refresh()
  loadUsers()
  loadMe()
})
</script>

<style scoped>
.admin-shell {
  position: relative;
  min-height: 100vh;
  background: var(--bg);
}

.topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 28px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
}

.back {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 12px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--teal-800);
  transition: background 0.15s ease;
}

.back:hover {
  background: var(--teal-100);
}

.top-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.top-title h1 {
  margin: 0;
  font-size: 17px;
  font-weight: 650;
}

.count {
  font-size: 12.5px;
  color: var(--muted);
}

.tabs {
  display: flex;
  gap: 4px;
  margin-left: auto;
  padding: 3px;
  border-radius: 11px;
  background: #eef4f2;
}

.tabs button {
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7f79;
  transition: all 0.15s ease;
}

.tabs button.active {
  color: var(--teal-800);
  background: #fff;
  box-shadow: 0 1px 3px rgba(20, 60, 50, 0.12);
}

.create-form {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.create-form input:not([type='checkbox']) {
  flex: 1;
  min-width: 150px;
  padding: 10px 13px;
  border: 1px solid var(--line);
  border-radius: 10px;
  font-size: 14px;
  background: #fbfdfc;
  transition: border-color 0.15s ease;
}

.create-form input:not([type='checkbox']):focus {
  border-color: var(--teal-600);
  outline: none;
}

.checkbox {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  color: #4d615b;
  white-space: nowrap;
  cursor: pointer;
}

.checkbox input {
  width: 15px;
  height: 15px;
  accent-color: var(--teal-700);
}

.user-item {
  flex-wrap: wrap;
}

.avatar {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 50%;
  font-size: 15px;
  font-weight: 700;
  color: var(--teal-700);
  background: var(--teal-100);
}

.me {
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
}

.text-btn {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--teal-700);
  transition: background 0.15s ease;
}

.text-btn:hover:not(:disabled) {
  background: var(--teal-100);
}

.text-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.content {
  max-width: 860px;
  margin: 0 auto;
  padding: 28px 24px 40px;
  display: grid;
  gap: 20px;
}

.upload-card,
.list-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 22px;
  box-shadow: var(--shadow-sm);
}

.upload-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.upload-head h2,
.list-head h2 {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 650;
}

.upload-head p {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.6;
}

.upload-btn {
  flex-shrink: 0;
  padding: 10px 18px;
  border-radius: 11px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(120deg, var(--teal-700), var(--teal-600));
  box-shadow: 0 8px 18px rgba(14, 124, 107, 0.22);
  transition: transform 0.16s ease, opacity 0.16s ease;
}

.upload-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.upload-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.mini-spinner {
  display: inline-block;
  width: 15px;
  height: 15px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.mini-spinner.dark {
  border-color: rgba(14, 124, 107, 0.25);
  border-top-color: var(--teal-700);
}

.picked {
  margin: 14px 0 0;
  font-size: 13px;
  color: var(--teal-700);
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.list-head .hint {
  font-size: 12px;
  color: #9aaba5;
}

.batch-btn {
  flex-shrink: 0;
  padding: 7px 14px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  color: var(--teal-700);
  background: var(--teal-100);
  transition: background 0.15s ease;
}

.batch-btn:hover:not(:disabled) {
  background: #d9f0e9;
}

.batch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.empty {
  padding: 30px 0;
  text-align: center;
  font-size: 13.5px;
  color: var(--muted);
}

.doc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 12px;
  border-radius: 11px;
  transition: background 0.15s ease;
}

.doc-item:hover {
  background: #f4f9f7;
}

.doc-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 9px;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #fff;
  background: linear-gradient(135deg, var(--teal-700), var(--teal-600));
}

.doc-icon.pdf {
  background: linear-gradient(135deg, #e46a8a, #cf5777);
}

.doc-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.4;
}

.doc-name {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-sub {
  font-size: 12px;
  color: var(--muted);
}

.badge {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11.5px;
  color: #b3772f;
  background: #fbf1e3;
}

.badge.ok {
  color: var(--teal-700);
  background: var(--teal-100);
}

.re {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 8px;
  color: #9aaba5;
  transition: all 0.15s ease;
}

.re:hover:not(:disabled) {
  color: var(--teal-700);
  background: var(--teal-100);
}

.re:disabled {
  cursor: not-allowed;
}

.del {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 8px;
  color: #9aaba5;
  transition: all 0.15s ease;
}

.del:hover {
  color: #e85a7a;
  background: #fde7ee;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(18, 32, 28, 0.42);
  backdrop-filter: blur(2px);
}

.modal {
  display: flex;
  flex-direction: column;
  width: min(720px, 100%);
  max-height: min(78vh, 720px);
  overflow: hidden;
  background: var(--card);
  border-radius: 16px;
  box-shadow: var(--shadow-md);
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line);
}

.modal-head h3 {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 650;
}

.modal-sub {
  font-size: 12.5px;
  color: var(--muted);
}

.modal-close {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 8px;
  color: #9aaba5;
  transition: all 0.15s ease;
}

.modal-close:hover {
  color: var(--teal-700);
  background: var(--teal-100);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 18px 20px;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}

.session-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.session-list li:hover {
  background: #f4f9f7;
}

.session-title {
  font-size: 14px;
  font-weight: 550;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--muted);
}

.back-link {
  margin-bottom: 10px;
}

.msg-list {
  display: grid;
  gap: 12px;
}

.msg {
  max-width: 86%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13.5px;
  line-height: 1.65;
}

.msg.user {
  margin-left: auto;
  color: #fff;
  background: linear-gradient(120deg, var(--teal-700), var(--teal-600));
  border-bottom-right-radius: 4px;
}

.msg.assistant {
  color: #22332e;
  background: #f3f8f6;
  border-bottom-left-radius: 4px;
}

.msg-role {
  margin-bottom: 3px;
  font-size: 11px;
  opacity: 0.7;
}

.msg-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
  z-index: 60;
  transform: translateX(-50%);
  padding: 10px 18px;
  font-size: 13px;
  color: #fff;
  background: rgba(20, 33, 30, 0.92);
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

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .content {
    padding: 20px 14px 32px;
  }

  .upload-head {
    flex-direction: column;
    align-items: stretch;
  }

  .upload-btn {
    width: 100%;
  }
}
</style>
