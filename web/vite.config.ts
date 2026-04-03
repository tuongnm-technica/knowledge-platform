import { defineConfig } from 'vite';
import injectHTML from 'vite-plugin-html-inject';

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
    emptyOutDir: true,
    chunkSizeWarningLimit: 800, // Tăng nhẹ giới hạn cảnh báo lên 800kB
    rollupOptions: {
      output: {
        manualChunks: {
          // Tách riêng các thư viện nặng ra các file js độc lập
          'vendor-tiptap': ['@tiptap/core', '@tiptap/starter-kit', 'tiptap-markdown', '@tiptap/suggestion'],
          'vendor-chart': ['chart.js'],
          'vendor-ui': ['tippy.js'],
          'vendor-utils': ['marked', 'dompurify', 'i18next'],
          'vendor-core': ['navigo']
        }
      }
    }
  }
});