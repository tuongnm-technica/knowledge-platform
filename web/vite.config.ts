import { defineConfig } from 'vite';
import { injectHTML } from 'vite-plugin-html-inject';

export default defineConfig({
  plugins: [injectHTML()],
  server: {
    port: 3000,
    proxy: {
      // Trỏ các request bắt đầu bằng /api về backend Python
      '/api': {
        target: 'http://localhost:8000', 
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
});