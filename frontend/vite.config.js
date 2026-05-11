import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8001'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 8888,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/frames': {
        target: backendTarget,
        changeOrigin: true
      },
      '/storage': {
        target: backendTarget,
        changeOrigin: true
      }
    }
  }
})
