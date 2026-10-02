import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server on 5173 (matches the backend CORS default); /api and /ws are not
// proxied — the Axios layer uses absolute VITE_API_BASE_URL instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
})
