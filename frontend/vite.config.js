import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to the Python backend WITHOUT rewriting the path.
//
// That matters: on Vercel, a service receives the original request path, so
// `GET /api/health` arrives at FastAPI as `/api/health`. Stripping the prefix here
// would make local work and production 404, which is exactly the class of problem
// Phase 3 exists to catch early.
//
// BACKEND_URL lets docker-compose point at the `backend` service by name, while a
// bare `npm run dev` on the host falls back to localhost.
const backend = process.env.BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // listen on 0.0.0.0 so the container is reachable
    port: 5173,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
    },
  },
})
