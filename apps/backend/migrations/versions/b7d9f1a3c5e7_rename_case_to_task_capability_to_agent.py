"""rename case -> task and capability -> agent in the database

Tables (aof_case -> aof_task, aof_case_item -> aof_task_item, aof_case_dataset ->
aof_task_dataset, aof_case_message -> aof_task_message, aof_capability_version ->
aof_agent_version), every column, index, constraint and sequence whose name says
case or capability (case_id -> task_id, capability_id -> agent_id, case_key ->
task_key, ...), the stored agent, group and task configurations (keys and
templates: `case:` -> `task:`, $case.cob -> $task.cob, case.label -> task.label),
and the JSON keys and kinds the platform writes itself. What people and connectors
wrote — comments, explanations, connector rows, tool arguments — is left as it was.

Revision ID: b7d9f1a3c5e7
Revises: e7f9a1b3c5d7
"""
import json
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d9f1a3c5e7"
down_revision: Union[str, Sequence[str], None] = "e7f9a1b3c5d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UP = {"case": "task", "cases": "tasks", "capability": "agent", "capabilities": "agents"}
DOWN = {"task": "case", "tasks": "cases", "agent": "capability", "agents": "capabilities"}
TABLES = {"aof_case": "aof_task", "aof_case_item": "aof_task_item", "aof_case_dataset": "aof_task_dataset",
          "aof_case_message": "aof_task_message", "aof_capability_version": "aof_agent_version"}
# English, not the platform's words: kept in configuration text.
PHRASES = re.compile(r"\b(use[- ]cases?|test cases?|edge cases?|worst[- ]case|best[- ]case|corner cases?|business cases?|"
                     r"lower[- ]case|upper[- ]case|title[- ]case|case[- ](?:in)?sensitive|case by case|in any case|"
                     r"in (?:that|which|either|most|some|many|both|such|rare|other) cases?|is the case|just in case|"
                     r"in case of|special cases?)\b", re.I)
WORD = re.compile(r"[A-Za-z0-9_]+")
PART = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+|_")


def _part(p: str, words: dict) -> str:
    new = words.get(p.lower())
    if not new:
        return p
    if p.isupper() and len(p) > 1:
        return new.upper()
    return new[0].upper() + new[1:] if p[0].isupper() else new


def _token(tok: str, words: dict) -> str:
    parts = PART.findall(tok)
    return "".join(_part(p, words) for p in parts) if "".join(parts) == tok else tok


def _text(s: str, words: dict) -> str:
    kept: list[str] = []

    def hold(m):
        kept.append(m.group(0))
        return f"\x00{len(kept) - 1}\x00"
    s = PHRASES.sub(hold, s) if words is UP else s
    s = WORD.sub(lambda m: _token(m.group(0), words), s)
    if words is UP:
        s = re.sub(r"(?<![A-Za-z0-9])([Aa])([ _-])([Aa]gent)(?![a-z])", r"\1n\2\3", s)
    else:
        s = re.sub(r"(?<![A-Za-z0-9])([Aa])n([ _-])([Cc]apability)", r"\1\2\3", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: kept[int(m.group(1))], s)


def _keys(v, words: dict):
    """The platform's own JSON: keys renamed, values as they were."""
    if isinstance(v, dict):
        return {_token(k, words): _keys(x, words) for k, x in v.items()}
    if isinstance(v, list):
        return [_keys(x, words) for x in v]
    return v


def _all(v, words: dict):
    """A configuration: keys and text renamed, as its YAML file was."""
    if isinstance(v, dict):
        return {_token(k, words): _all(x, words) for k, x in v.items()}
    if isinstance(v, list):
        return [_all(x, words) for x in v]
    return _text(v, words) if isinstance(v, str) else v


def _rewrite(bind, table: str, key: list[str], column: str, fn, words: dict) -> None:
    rows = bind.execute(sa.text(f'SELECT {", ".join(key)}, "{column}" FROM {table} WHERE "{column}" IS NOT NULL')).all()
    for row in rows:
        old = row[-1]
        new = fn(old, words)
        if new != old:
            where = " AND ".join(f'"{k}" = :k{i}' for i, k in enumerate(key))
            bind.execute(sa.text(f'UPDATE {table} SET "{column}" = CAST(:v AS JSONB) WHERE {where}'),
                         {"v": json.dumps(new), **{f"k{i}": row[i] for i in range(len(key))}})


def _names(bind, words: dict, tables: dict) -> None:
    for old, new in tables.items():
        op.rename_table(old, new)
    aof = "c.relname LIKE 'aof\\_%'"
    for table, column in bind.execute(sa.text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name LIKE 'aof\\_%'")).all():
        new = _token(column, words)
        if new != column:
            op.alter_column(table, column, new_column_name=new)
    for table, name in bind.execute(sa.text(
            f"SELECT c.relname, k.conname FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid "
            f"WHERE {aof} AND c.relnamespace = current_schema()::regnamespace")).all():
        new = _token(name, words)
        if new != name:
            op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{name}" TO "{new}"')
    for (name,) in bind.execute(sa.text(
            "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND tablename LIKE 'aof\\_%'")).all():
        new = _token(name, words)
        if new != name and bind.execute(sa.text("SELECT to_regclass(:n)"), {"n": name}).scalar() is not None:
            op.execute(f'ALTER INDEX "{name}" RENAME TO "{new}"')
    for (name,) in bind.execute(sa.text(
            "SELECT sequence_name FROM information_schema.sequences "
            "WHERE sequence_schema = current_schema() AND sequence_name LIKE 'aof\\_%'")).all():
        new = _token(name, words)
        if new != name:
            op.execute(f'ALTER SEQUENCE "{name}" RENAME TO "{new}"')


def _data(bind) -> None:
    _rewrite(bind, "aof_agent_version", ["agent_id", "version"], "manifest", _all, UP)
    _rewrite(bind, "aof_group_version", ["agent_id", "group_id", "version"], "config", _all, UP)
    _rewrite(bind, "aof_task", ["task_id"], "manifest", _all, UP)
    for column in ("draft", "clock_state"):
        _rewrite(bind, "aof_task", ["task_id"], column, _keys, UP)
    for column in ("finding", "priors"):
        _rewrite(bind, "aof_proposal_group", ["task_id", "group_id"], column, _keys, UP)
    for column in ("summary", "results"):
        _rewrite(bind, "aof_eval_run", ["run_id"], column, _keys, UP)
    _rewrite(bind, "aof_task_message", ["message_id"], "meta", _keys, UP)
    _rewrite(bind, "aof_kg_node", ["namespace", "node_id", "valid_from"], "attrs", _keys, UP)
    _rewrite(bind, "aof_switch", ["kind", "target"], "history", _keys, UP)
    for table, column in (("aof_switch", "kind"), ("aof_notification", "kind")):
        for (value,) in bind.execute(sa.text(f'SELECT DISTINCT "{column}" FROM {table}')).all():
            new = _token(value, UP)
            if new != value:
                bind.execute(sa.text(f'UPDATE {table} SET "{column}" = :new WHERE "{column}" = :old'),
                             {"new": new, "old": value})


def _config_down(v, top=True):
    """Back to the old configuration keys: the task section and its templates. Text and
    other JSON stay in the new words (a downgrade restores what the old code reads)."""
    if isinstance(v, dict):
        return {("case" if k == "task" else _token(k, DOWN) if k.startswith("task_") or k.endswith("_task")
                 else k): _config_down(x, False) for k, x in v.items()}
    if isinstance(v, list):
        return [_config_down(x, False) for x in v]
    if isinstance(v, str):
        return re.sub(r"\$task(?=[._])", "$case", re.sub(r"^task\.", "case.", v))
    return v


def upgrade() -> None:
    bind = op.get_bind()
    _names(bind, UP, TABLES)
    _data(bind)


def downgrade() -> None:
    """Names, and the configuration keys the old code reads; the rest stays renamed."""
    bind = op.get_bind()
    _rewrite(bind, "aof_agent_version", ["agent_id", "version"], "manifest", lambda v, _: _config_down(v), DOWN)
    _rewrite(bind, "aof_group_version", ["agent_id", "group_id", "version"], "config", lambda v, _: _config_down(v), DOWN)
    _rewrite(bind, "aof_task", ["task_id"], "manifest", lambda v, _: _config_down(v), DOWN)
    _names(bind, DOWN, {new: old for old, new in TABLES.items()})
