import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    preserveSymlinks: true,
  },
  server: {
    fs: { strict: false },
  },
  test: {
    include: ['tests/frontend/**/*.test.js'],
    environment: 'node',
    globals: true,
    pool: 'forks',
    passWithNoTests: false,
    server: {
      deps: {
        inline: [/.*/],
      },
    },
    // Workaround: alias to handle '#' in workspace path (Mega Folder/#3)
    alias: {
      '~tests': './tests/frontend',
    },
  },
});
