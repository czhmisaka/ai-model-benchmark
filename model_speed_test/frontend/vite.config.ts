import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 14001,
    proxy: {
      '/api': {
        target: 'http://localhost:15010',
        changeOrigin: true
      },
      '/config': {
        target: 'http://localhost:15010',
        changeOrigin: true
      },
      '/test': {
        target: 'http://localhost:15010',
        changeOrigin: true
      },
      '/events': {
        target: 'http://localhost:15010',
        changeOrigin: true,
        ws: true
      },
      '/status': {
        target: 'http://localhost:15010',
        changeOrigin: true
      },
      '/reset': {
        target: 'http://localhost:15010',
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        // 大体积依赖单独分包：echarts 仅 History 页使用，加快首屏加载
        manualChunks: {
          echarts: ['echarts']
        }
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {}
    }
  }
})