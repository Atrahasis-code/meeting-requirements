import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0', port: 8080, strictPort: true,
    proxy: { '/api': 'http://backend:8000', '/auth/callback': 'http://backend:8000' },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], css: false },
})
