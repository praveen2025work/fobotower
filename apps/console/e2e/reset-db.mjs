import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const api = fileURLToPath(new URL('../../api', import.meta.url));

execFileSync('.venv/bin/python', ['scripts/reset_e2e_db.py'], {
  cwd: api,
  stdio: 'inherit',
  env: {
    ...process.env,
    FOBO_DATABASE_URL: 'postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_e2e',
  },
});
