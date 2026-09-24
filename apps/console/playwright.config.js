import { defineConfig } from '@playwright/test';

const API = 'http://localhost:8101';
const CONSOLE = 'http://localhost:3101';

export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  workers: 1,
  use: { baseURL: CONSOLE, trace: 'retain-on-failure' },
  webServer: [
    {
      command: '.venv/bin/uvicorn api.main:app --port 8101',
      cwd: '../api',
      url: `${API}/health`,
      env: {
        FOBO_ENV: 'dev',
        FOBO_DATABASE_URL: 'postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_e2e',
        FOBO_CONSOLE_ORIGINS: CONSOLE,
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npx next dev -p 3101',
      url: `${CONSOLE}/fobo`,
      env: { NEXT_PUBLIC_API_BASE: API, NEXT_DIST_DIR: '.next-e2e' },
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
