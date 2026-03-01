import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 360_000,
  retries: 0,
  use: {
    baseURL: process.env.API_BASE_URL || 'http://localhost:8200/api/v1',
    extraHTTPHeaders: {
      'Content-Type': 'application/json',
    },
  },
  reporter: [['list'], ['html', { open: 'never' }]],
});
