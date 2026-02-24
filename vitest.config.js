import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    preserveSymlinks: true,
  },
  server: {
    fs: { strict: false },
  },
  test: {
    include: ['extension/__tests__/**/*.test.js'],
    environment: 'node',
    globals: true,
    pool: 'forks',
    server: {
      deps: {
        inline: [/.*/],
      },
    },
  },
});
