import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Where the FastAPI backend is listening. Override with BACKEND_URL if port
// 8000 is taken (another homework's backend may already be using it).
const backend = process.env.BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxying keeps the browser on one origin, so no API base URL or
    // credential is ever baked into the bundle.
    proxy: { '/api': { target: backend, changeOrigin: true } },
  },
})
