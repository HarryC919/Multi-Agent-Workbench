import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: [
    './tests/**/*.test.ts',
    './tests/**/*.test.tsx',
    './tests/**/*.bench.ts',
    './tests/**/*.bench.tsx',
  ],
    // Bench: keep them in regular test run so CI exercises timing.
    exclude: ['node_modules', 'dist'],
  },
})