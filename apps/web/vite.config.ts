import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  // Bake the short git commit into the bundle at build time. The image build
  // passes GIT_COMMIT (see apps/web/Dockerfile + the Makefile deploy target);
  // local dev / tests fall back to 'dev'.
  define: {
    __GIT_COMMIT__: JSON.stringify(process.env.GIT_COMMIT ?? 'dev'),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL ?? 'http://api:8000',
        changeOrigin: true,
      },
    },
  },
});
