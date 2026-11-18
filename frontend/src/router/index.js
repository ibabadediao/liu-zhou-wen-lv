import { createRouter, createWebHistory } from 'vue-router'
import { loadMe } from '../store/auth'
import LoginView from '../views/LoginView.vue'
import ChatView from '../views/ChatView.vue'
import AdminView from '../views/AdminView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { guestOnly: true },
    },
    {
      path: '/chat',
      name: 'chat',
      component: ChatView,
      meta: { requiresAuth: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: AdminView,
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/chat' },
  ],
})

// 路由守卫: 未登录只能进登录页, 已登录不再回登录页, 非管理员不进管理页
router.beforeEach(async (to) => {
  const user = await loadMe()

  if (to.meta.requiresAuth && !user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && user) {
    return { name: 'chat' }
  }
  if (to.meta.requiresAdmin && !user?.is_admin) {
    return { name: 'chat' }
  }
  return true
})

export default router
