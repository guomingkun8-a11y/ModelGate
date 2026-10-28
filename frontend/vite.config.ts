import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({ plugins: [vue()], server: { port: 5173, strictPort: true, proxy: { '/internal': 'http://127.0.0.1:8010', '/v1': 'http://127.0.0.1:8010', '/healthz': 'http://127.0.0.1:8010' } }, build: { chunkSizeWarningLimit: 1200 } })
