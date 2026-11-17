import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发态将后端接口代理到 8000 端口, 使 Cookie 保持同源(浏览器按 host 存 Cookie, 端口不同不影响)
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
