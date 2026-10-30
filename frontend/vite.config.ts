import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = process.env.MODELGATE_BACKEND_URL || 'http://127.0.0.1:8012'

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.MODELGATE_FRONTEND_PORT || 5175),
    strictPort: true,
    proxy: {
      '/internal': backendTarget,
      '/v1': backendTarget,
      '/healthz': backendTarget,
    },
  },
})
