import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';

// Inlines every asset into one .html. That file is both the shareable offline export
// and what the Streamlit calibration tab embeds, so a teammate without Node (or
// without wifi, which is the normal state of a competition venue) can still use it.
// server/export.py injects window.__MATCH_SPEC__ ahead of the bundle.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  // The dev fixture in public/ must not be copied into the committed bundle --
  // it is a 2MB sample log that the standalone export has no use for.
  publicDir: false,
  build: {
    outDir: '../server/assets',
    emptyOutDir: false,
    rollupOptions: { output: { entryFileNames: 'player.js' } },
  },
});
