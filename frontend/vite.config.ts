import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { sentryVitePlugin } from '@sentry/vite-plugin'
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig(({ mode, command }) => {
  const isProduction = mode === 'production'
  const root = fileURLToPath(new URL('.', import.meta.url))
  const env = loadEnv(mode, root, '')
  // Build-only token file; never expose SENTRY_* values via Vite's client env.
  const sentryEnv = loadEnv('sentry-build-plugin', root, 'SENTRY_')
  const authToken = sentryEnv.SENTRY_AUTH_TOKEN?.trim()
  const uploadRequested = sentryEnv.SENTRY_UPLOAD_SOURCEMAPS
  const uploadSourceMaps = command === 'build' &&
    (uploadRequested === 'true' || (uploadRequested !== 'false' && Boolean(authToken)))
  if (uploadSourceMaps && !authToken) {
    throw new Error('SENTRY_AUTH_TOKEN is required when SENTRY_UPLOAD_SOURCEMAPS=true')
  }
  const desktopVersion = JSON.parse(readFileSync(new URL('../src-tauri/tauri.conf.json', import.meta.url), 'utf8')).version
  const appVersion = env.VITE_APP_VERSION || desktopVersion
  
  return {
    plugins: [
      react(),
      ...(uploadSourceMaps ? [sentryVitePlugin({
        org: sentryEnv.SENTRY_ORG || 'autoclip-ts',
        project: sentryEnv.SENTRY_PROJECT || 'autoclip-frontend',
        authToken,
        telemetry: false,
        release: {
          // Must match src/desktop/sentry.ts exactly.
          name: `autoclip-frontend@${appVersion}`,
          inject: false,
        },
        sourcemaps: {
          assets: `${root}dist/**`,
          filesToDeleteAfterUpload: [`${root}dist/**/*.map`],
        },
      })] : []),
    ],
    define: {
      'import.meta.env.VITE_APP_VERSION': JSON.stringify(appVersion),
    },
    base: isProduction ? './' : '/', // 生产环境使用相对路径
    optimizeDeps: {
      include: ['@tauri-apps/api', '@tauri-apps/api/dialog']
    },
    build: {
      sourcemap: uploadSourceMaps ? 'hidden' : false,
      assetsInlineLimit: 4096,
      chunkSizeWarningLimit: 1600,
      rollupOptions: {
        external: [],
        // NOTE: do NOT hand-split React and antd into separate vendor chunks.
        // antd's top-level code calls React.createContext at module-eval time;
        // when React and antd are in different chunks, the chunk load order is
        // not guaranteed and antd can evaluate before React's CJS-interop is
        // initialized, leaving `React` undefined → "Cannot read properties of
        // undefined (reading 'createContext')" → blank/black screen. Letting
        // Rollup decide chunking keeps React's evaluation ordered correctly.
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
          // Override when the desktop backend (random port) is running: BACKEND_URL=http://127.0.0.1:PORT npm run dev
          target: process.env.BACKEND_URL || 'http://localhost:8000',
          changeOrigin: true
        }
      }
    }
  }
})
