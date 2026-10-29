import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/internal': 'http://127.0.0.1:8010',
      '/v1': 'http://127.0.0.1:8010',
      '/healthz': 'http://127.0.0.1:8010',
    },
  },
})
