import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production'
  
  return {
    plugins: [react()],
    base: isProduction ? './' : '/', // 生产环境使用相对路径
    optimizeDeps: {
      include: ['@tauri-apps/api', '@tauri-apps/api/dialog']
    },
    build: {
      sourcemap: false,
      assetsInlineLimit: 4096,
      chunkSizeWarningLimit: 700,
      rollupOptions: {
        external: [],
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('antd') || id.includes('@ant-design')) {
                return 'vendor-antd'
              }
              if (id.includes('react') || id.includes('react-dom') || id.includes('react-router-dom')) {
                return 'vendor-react'
              }
              if (id.includes('react-player')) {
                return 'vendor-player'
              }
              return 'vendor-misc'
            }
            return undefined
          }
        }
      },
      // 生产环境禁用 Service Worker
      serviceWorker: false
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 3000,
      strictPort: true, // 如果端口被占用则报错，而不是自动切换
      hmr: {
        overlay: false // 禁用错误覆盖层
      },
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true
        }
      }
    }
  }
})