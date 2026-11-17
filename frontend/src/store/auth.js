import { reactive } from 'vue'
import { authApi } from '../api'

/**
 * 全局登录态
 * 注意: 只在前端内存保存用户信息, 凭证本身在 httpOnly Cookie 中, JS 无法读取
 */
export const auth = reactive({
  user: null,
  ready: false,
})

export async function loadMe(force = false) {
  if (auth.ready && !force) return auth.user
  try {
    const data = await authApi.me()
    auth.user = data.user
  } catch {
    auth.user = null
  }
  auth.ready = true
  return auth.user
}

export async function login(username, password) {
  const data = await authApi.login(username, password)
  auth.user = data.user
  auth.ready = true
  return data.user
}

export async function register(username, password) {
  const data = await authApi.register(username, password)
  auth.user = data.user
  auth.ready = true
  return data.user
}

export async function logout() {
  try {
    await authApi.logout()
  } finally {
    auth.user = null
    auth.ready = true
  }
}
