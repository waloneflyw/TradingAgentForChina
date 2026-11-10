import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 前端独立端口 5173，后端 FastAPI 8000。dev 环境用代理转发 /api（后端已开 CORS *，双保险）。
// host: true 让 dev/preview 服务监听 0.0.0.0，局域网其他机器可通过本机 IP 访问。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: true,
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
