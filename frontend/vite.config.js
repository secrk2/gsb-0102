import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 本地开发：/api 代理到本机 8000 的 FastAPI；容器内由 nginx 反代
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
