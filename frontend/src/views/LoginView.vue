<template>
  <div class="auth-page">
    <section class="brand">
      <div class="glow glow-a"></div>
      <div class="glow glow-b"></div>
      <div class="brand-rings"></div>

      <header class="brand-top">
        <span class="logo">柳</span>
        <span class="brand-name">柳州文旅智能体</span>
      </header>

      <div class="brand-main">
        <p class="eyebrow">LIUZHOU · GUANGXI</p>
        <h1>一条柳江，<br />半城山水半城粉。</h1>
        <p class="desc">
          景点咨询、螺蛳粉探店、两日游路线，交给一个会看天气、懂本地的 AI 旅行搭子。
        </p>
        <ul class="features">
          <li><em>01</em> 本地知识库，景点美食张口就来</li>
          <li><em>02</em> 实时天气联动，行程随时可调</li>
          <li><em>03</em> 会话按账号隔离，旅途计划只属于你</li>
        </ul>
      </div>

      <footer class="brand-foot">紫荆花城 · 螺蛳粉故乡 · 百里柳江</footer>
    </section>

    <section class="panel">
      <div class="card">
        <div class="tabs">
          <button
            type="button"
            :class="{ active: mode === 'login' }"
            @click="switchMode('login')"
          >
            登录
          </button>
          <button
            type="button"
            :class="{ active: mode === 'register' }"
            @click="switchMode('register')"
          >
            注册
          </button>
        </div>

        <h2>{{ mode === 'login' ? '欢迎回来' : '创建账号' }}</h2>
        <p class="sub">
          {{ mode === 'login' ? '登录后继续你的柳州之旅' : '注册后即可开始规划专属行程' }}
        </p>

        <form @submit.prevent="submit">
          <label class="field">
            <span>用户名</span>
            <input
              v-model.trim="username"
              type="text"
              autocomplete="username"
              placeholder="3-32 位字符"
              maxlength="32"
              required
            />
          </label>

          <label class="field">
            <span>密码</span>
            <input
              v-model="password"
              type="password"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              placeholder="至少 6 位"
              maxlength="64"
              required
            />
          </label>

          <p class="error" v-if="error">{{ error }}</p>

          <button class="submit" type="submit" :disabled="loading">
            <span v-if="!loading">{{ mode === 'login' ? '登 录' : '注 册' }}</span>
            <span v-else class="spinner"></span>
          </button>
        </form>

        <p class="switch">
          <template v-if="mode === 'login'">
            还没有账号？<button type="button" @click="switchMode('register')">立即注册</button>
          </template>
          <template v-else>
            已有账号？<button type="button" @click="switchMode('login')">返回登录</button>
          </template>
        </p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, register } from '../store/auth'

const router = useRouter()
const route = useRoute()

const mode = ref('login')
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

function switchMode(next) {
  mode.value = next
  error.value = ''
}

async function submit() {
  error.value = ''

  if (username.value.length < 3) {
    error.value = '用户名至少 3 位'
    return
  }
  if (password.value.length < 6) {
    error.value = '密码至少 6 位'
    return
  }

  loading.value = true
  try {
    if (mode.value === 'login') {
      await login(username.value, password.value)
    } else {
      await register(username.value, password.value)
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/chat'
    router.replace(redirect)
  } catch (e) {
    error.value = e.message || '操作失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  min-height: 100vh;
}

/* ============ 左侧品牌区 ============ */
.brand {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 44px 56px;
  color: #eaf7f3;
  background: linear-gradient(155deg, #06302a 0%, #0a5548 46%, #0e7c6b 100%);
}

.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.55;
  pointer-events: none;
}

.glow-a {
  width: 420px;
  height: 420px;
  right: -110px;
  top: -120px;
  background: #26c2a5;
}

.glow-b {
  width: 320px;
  height: 320px;
  left: -90px;
  bottom: -120px;
  background: #e46a8a;
  opacity: 0.35;
}

.brand-rings {
  position: absolute;
  right: -180px;
  bottom: -220px;
  width: 560px;
  height: 560px;
  border-radius: 50%;
  border: 1px solid rgba(234, 247, 243, 0.14);
  box-shadow: 0 0 0 60px rgba(234, 247, 243, 0.045),
    0 0 0 130px rgba(234, 247, 243, 0.03);
  pointer-events: none;
}

.brand-top {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.logo {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.22);
  font-size: 20px;
  font-weight: 700;
}

.brand-main {
  position: relative;
  max-width: 520px;
  margin: 40px 0;
}

.eyebrow {
  margin: 0 0 18px;
  font-size: 12px;
  letter-spacing: 3px;
  color: rgba(234, 247, 243, 0.65);
}

.brand-main h1 {
  margin: 0;
  font-size: clamp(30px, 3.6vw, 46px);
  line-height: 1.32;
  font-weight: 700;
  letter-spacing: 1px;
}

.desc {
  margin: 20px 0 30px;
  font-size: 15px;
  line-height: 1.85;
  color: rgba(234, 247, 243, 0.78);
}

.features {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 14px;
}

.features li {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: rgba(234, 247, 243, 0.9);
}

.features em {
  font-style: normal;
  font-size: 11px;
  letter-spacing: 1px;
  color: #8fe3d1;
  border: 1px solid rgba(143, 227, 209, 0.4);
  border-radius: 999px;
  padding: 3px 9px;
}

.brand-foot {
  position: relative;
  font-size: 12px;
  letter-spacing: 2px;
  color: rgba(234, 247, 243, 0.45);
}

/* ============ 右侧表单区 ============ */
.panel {
  display: grid;
  place-items: center;
  padding: 40px 24px;
  background: radial-gradient(circle at 80% 12%, #eef7f3 0%, #f7faf8 48%, #ffffff 100%);
}

.card {
  width: 100%;
  max-width: 396px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 22px;
  padding: 34px 34px 28px;
  box-shadow: var(--shadow-md);
  animation: rise 0.45s ease both;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
}

.tabs {
  display: inline-flex;
  padding: 4px;
  gap: 4px;
  border-radius: 12px;
  background: #f1f6f4;
  margin-bottom: 26px;
}

.tabs button {
  padding: 7px 22px;
  border-radius: 9px;
  font-size: 14px;
  color: var(--muted);
  transition: all 0.2s ease;
}

.tabs button.active {
  background: #fff;
  color: var(--teal-800);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.card h2 {
  margin: 0 0 8px;
  font-size: 25px;
  letter-spacing: 0.5px;
}

.sub {
  margin: 0 0 26px;
  font-size: 13.5px;
  color: var(--muted);
}

.field {
  display: block;
  margin-bottom: 16px;
}

.field span {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #3c5a52;
}

.field input {
  width: 100%;
  padding: 12px 14px;
  font-size: 14.5px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: #fbfdfc;
  outline: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.field input:focus {
  border-color: var(--teal-600);
  background: #fff;
  box-shadow: 0 0 0 4px rgba(18, 144, 124, 0.12);
}

.error {
  margin: 2px 0 14px;
  padding: 9px 12px;
  font-size: 13px;
  color: #b4374f;
  background: #fdf0f3;
  border: 1px solid #f7d6de;
  border-radius: 9px;
}

.submit {
  width: 100%;
  height: 46px;
  margin-top: 6px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 3px;
  background: linear-gradient(120deg, var(--teal-700), var(--teal-600));
  box-shadow: 0 10px 22px rgba(14, 124, 107, 0.26);
  transition: transform 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease;
}

.submit:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 14px 26px rgba(14, 124, 107, 0.32);
}

.submit:disabled {
  opacity: 0.75;
  cursor: not-allowed;
}

.spinner {
  width: 19px;
  height: 19px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.switch {
  margin: 18px 0 0;
  text-align: center;
  font-size: 13px;
  color: var(--muted);
}

.switch button {
  color: var(--teal-700);
  font-weight: 600;
  padding: 0;
}

@media (max-width: 900px) {
  .auth-page {
    grid-template-columns: 1fr;
  }

  .brand {
    padding: 30px 26px 34px;
  }

  .brand-main {
    margin: 28px 0 10px;
  }

  .brand-main h1 {
    font-size: 28px;
  }

  .features,
  .brand-foot {
    display: none;
  }

  .panel {
    padding: 28px 18px 42px;
  }

  .card {
    padding: 26px 22px 22px;
  }
}
</style>
