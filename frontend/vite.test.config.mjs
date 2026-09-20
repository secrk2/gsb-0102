import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 仅用于把组件测试打成浏览器端 IIFE，随后在 jsdom 里执行
export default defineConfig({
  plugins: [vue()],
  logLevel: 'error',
  build: {
    write: true,
    outDir: '/tmp/huitang-test-build',
    emptyOutDir: true,
    minify: false,
    rollupOptions: {
      input: resolve('/workspace/frontend/tests/components.test.mjs'),
      output: {
        format: 'iife',
        name: 'HuitangTest',
        entryFileNames: 'suite.js',
      },
    },
  },
})
