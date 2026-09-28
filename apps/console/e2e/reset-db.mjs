import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const backend = fileURLToPath(new URL('../../backend', import.meta.url));

const python = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python';

execFileSync(python, ['scripts/reset_e2e_db.py'], {
  cwd: backend,
  stdio: 'inherit',
  env: {
    ...process.env,
    FOBO_DATABASE_URL: 'postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_e2e',
  },
});
