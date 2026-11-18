import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发态将后端接口代理到 8000 端口, 使 Cookie 保持同源(浏览器按 host 存 Cookie, 端口不同不影响)
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 一条正则合并所有后端前缀(以 ^ 开头表示按正则匹配), 前端页面/资源仍由 Vite 自己处理
      '^(/auth|/chat|/sessions|/health|/admin|/files)': 'http://localhost:8000',
    },
  },
})
