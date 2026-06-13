import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  // tsconfig ставит jsx:"preserve" (для vite), поэтому esbuild внутри vitest
  // по умолчанию компилирует JSX в classic-режиме без импорта React.
  esbuild: { jsx: 'automatic' },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./client/src/test-setup.ts'],
    include: ['client/src/**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './client/src'),
      '@shared': path.resolve(__dirname, './shared'),
    },
  },
});
