"""The checkpoint tables' indexes are created once, at process startup, not
lazily inside a request — see api/deps.py::setup_checkpointer for why doing
it lazily can deadlock forever on a brand-new database.

Reproducing that deadlock here directly would mean dropping the checkpoint
tables in the shared `fobo_test` database every other test in this suite
depends on, with no way to guarantee they are restored if an assertion
fails partway through — one broken test run would take the whole suite
down with it, and reliably reproducing a multi-minute Postgres lock wait
inside a fast, deterministic unit test is inherently timing-sensitive.
Instead these assert the two halves of the actual fix: a checkpointer()
call after the first one never re-runs setup, and the app's own lifespan is
what performs that first one, before any request can hold a transaction.
The real fresh-database scenario is covered end-to-end by
apps/console/e2e/workflow.spec.js, which boots the API against a brand-new
fobo_e2e database with nothing pre-warmed.
"""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

import api.deps as deps
from api.deps import checkpointer
from api.main import create_app


def _count_calls(monkeypatch):
    """Patches AsyncPostgresSaver.setup to count real invocations, while
    still running the real thing so the tables/indexes stay in place."""
    calls = {"n": 0}
    original = AsyncPostgresSaver.setup

    async def counting_setup(self):
        calls["n"] += 1
        await original(self)

    monkeypatch.setattr(AsyncPostgresSaver, "setup", counting_setup)
    return calls


async def test_checkpointer_never_reruns_setup_once_the_process_has_warmed_up(
    monkeypatch,
):
    """conftest's session fixture already ran setup once before any test
    runs — the same thing the app's lifespan does in production. Every
    later checkpointer() use, however many recs a board load opens, must
    not run it again."""
    calls = _count_calls(monkeypatch)

    async with checkpointer():
        pass
    async with checkpointer():
        pass

    assert calls["n"] == 0


async def test_the_apps_lifespan_creates_the_checkpoint_tables_before_serving(
    monkeypatch,
):
    """The one real setup call happens at startup, not inside a request —
    the actual fix: it can no longer run while a request's own session
    holds an open transaction."""
    calls = _count_calls(monkeypatch)
    was_ready = deps._checkpointer_ready
    deps._checkpointer_ready = False
    try:
        app = create_app()
        async with app.router.lifespan_context(app):
            pass
        assert calls["n"] == 1
    finally:
        deps._checkpointer_ready = was_ready
