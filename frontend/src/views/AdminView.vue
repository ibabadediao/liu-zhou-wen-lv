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
        <h1>知识库管理</h1>
        <span class="count">{{ documents.length }} 个文档</span>
      </div>
    </header>

    <main class="content">
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
          <h2>已入库文档</h2>
          <span class="hint">删除会同时移除源文件与向量数据</span>
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
            <button class="del" @click="removeDoc(d)" title="删除文档">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </li>
        </ul>
      </section>
    </main>

    <transition name="fade">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { kbApi, uploadKbDocument } from '../api'

const router = useRouter()

const documents = ref([])
const loading = ref(true)
const uploading = ref(false)
const picked = ref(null)
const toast = ref('')
const fileInput = ref(null)

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

onMounted(refresh)
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

.picked {
  margin: 14px 0 0;
  font-size: 13px;
  color: var(--teal-700);
}

.list-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.list-head .hint {
  font-size: 12px;
  color: #9aaba5;
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

.toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
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
