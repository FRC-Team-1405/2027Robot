import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The FastAPI server (janitor/server/main.py) mounts dist/ and answers /api. In dev, Vite serves the
// page with HMR and proxies /api to the server. Ports differ from logbench's (8765 / 5173) so both can run.
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5174,
    proxy: { '/api': { target: 'http://127.0.0.1:8767', changeOrigin: true } },
  },
});
