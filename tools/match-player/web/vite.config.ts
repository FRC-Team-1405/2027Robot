import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev + normal build. The FastAPI server (server/main.py) mounts dist/ and answers
// /api, so dev proxies /api to it and everything else is served by Vite with HMR.
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true } },
  },
});
