"""rename the platform's database objects: helix_* -> aof_* (Agent One Finance)

Tables, their indexes, constraints and sequences take the aof_ prefix; role
names stored in configuration and cases move from HELIX_ to AOF_; the
scheduler's user and the workflow checkpoints follow.

Revision ID: e7f9a1b3c5d7
Revises: d6e8f0a2b4c6
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e7f9a1b3c5d7"
down_revision: Union[str, Sequence[str], None] = "d6e8f0a2b4c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename(old: str, new: str, role_old: str, role_new: str, user_old: str, user_new: str, thread_old: str, thread_new: str) -> None:
    op.execute(f"""
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = current_schema() AND tablename LIKE '{old}%' LOOP
    EXECUTE format('ALTER TABLE %I RENAME TO %I', r.tablename, '{new}' || substr(r.tablename, {len(old) + 1}));
  END LOOP;
  FOR r IN SELECT c.conname, t.relname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
           WHERE t.relname LIKE '{new}%' AND c.conname LIKE '%{old.rstrip("_")}%' LOOP
    EXECUTE format('ALTER TABLE %I RENAME CONSTRAINT %I TO %I', r.relname, r.conname, replace(r.conname, '{old.rstrip("_")}', '{new.rstrip("_")}'));
  END LOOP;
  FOR r IN SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND indexname LIKE '%{old.rstrip("_")}%' LOOP
    EXECUTE format('ALTER INDEX %I RENAME TO %I', r.indexname, replace(r.indexname, '{old.rstrip("_")}', '{new.rstrip("_")}'));
  END LOOP;
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = current_schema() AND sequencename LIKE '{old}%' LOOP
    EXECUTE format('ALTER SEQUENCE %I RENAME TO %I', r.sequencename, '{new}' || substr(r.sequencename, {len(old) + 1}));
  END LOOP;
  -- role names and the scheduler user, wherever the platform stored them
  FOR r IN SELECT table_name, column_name, data_type FROM information_schema.columns
           WHERE table_schema = current_schema() AND table_name LIKE '{new}%'
             AND data_type IN ('jsonb', 'character varying', 'text') LOOP
    IF r.data_type = 'jsonb' THEN
      EXECUTE format('UPDATE %I SET %I = replace(replace(%I::text, %L, %L), %L, %L)::jsonb WHERE %I::text LIKE %L OR %I::text LIKE %L',
        r.table_name, r.column_name, r.column_name, '{role_old}', '{role_new}', '{user_old}', '{user_new}',
        r.column_name, '%{role_old}%', r.column_name, '%{user_old}%');
    ELSE
      EXECUTE format('UPDATE %I SET %I = replace(replace(%I, %L, %L), %L, %L) WHERE %I LIKE %L OR %I LIKE %L',
        r.table_name, r.column_name, r.column_name, '{role_old}', '{role_new}', '{user_old}', '{user_new}',
        r.column_name, '%{role_old}%', r.column_name, '%{user_old}%');
    END IF;
  END LOOP;
  -- the workflow's checkpoints, keyed by case
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = current_schema()
           AND tablename IN ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes') LOOP
    EXECUTE format('UPDATE %I SET thread_id = %L || substr(thread_id, %s) WHERE thread_id LIKE %L',
      r.tablename, '{thread_new}', {len(thread_old) + 1}, '{thread_old}%');
  END LOOP;
END $$;
""")


def upgrade() -> None:
    _rename("helix_", "aof_", "HELIX_", "AOF_", "helix-scheduler", "aof-scheduler", "helix:", "aof:")


def downgrade() -> None:
    _rename("aof_", "helix_", "AOF_", "HELIX_", "aof-scheduler", "helix-scheduler", "aof:", "helix:")
