import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  // Mirror vite.config's define so components reading __GIT_COMMIT__ render
  // under Vitest (it uses a separate config and won't inherit vite's define).
  define: {
    __GIT_COMMIT__: JSON.stringify(process.env.GIT_COMMIT ?? 'dev'),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    exclude: ['**/node_modules/**', '**/e2e/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: 'coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.d.ts',
        'src/main.tsx',
        'src/**/*.test.{ts,tsx}',
        'src/**/__mocks__/**',
        'src/api/types.ts',
        'src/theme.ts',
      ],
    },
  },
});
