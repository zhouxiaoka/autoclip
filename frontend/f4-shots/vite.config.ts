import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('../src', import.meta.url)),
      '@provider-presets': fileURLToPath(new URL('../../backend/presets/provider_presets.json', import.meta.url)),
      '@provider-quality': fileURLToPath(new URL('../../backend/presets/provider_quality.json', import.meta.url)),
      '@event-catalog': fileURLToPath(new URL('../../backend/core/event_catalog.json', import.meta.url)),
      '@failure-messages': fileURLToPath(new URL('../../backend/core/failure_messages.json', import.meta.url)),
    },
  },
  server: { port: 5204, strictPort: true, host: '127.0.0.1' },
})
