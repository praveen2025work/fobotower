"""Checkpoints written before the 2026-09-26 module rename.

Before this branch the contract models lived at `app.contracts.models`.
LangGraph's checkpoint serializer stores each value's module path and
resolves it back via `importlib.import_module` on read (see
`langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer`), so a checkpoint
written under the old path can no longer find its classes once that module
is gone: it silently falls back to a plain dict. `fobo/web/decisions.py`
reads `g.break_ids` off each pattern group, so a dict there raises
`AttributeError` and Approve/Reject returns 500 for every case whose
checkpoint predates the rename (sess-r-1055, sess-r-2031, sess-r-2048 in the
dev database).

`fobo/contracts/models.py` registers `app.contracts.models` as a
`sys.modules` alias of itself so those old checkpoints keep resolving to the
real types. These tests reproduce the old serialization exactly (mutating
`__module__` before encoding, the way the classes really were named back
then) rather than hand-editing msgpack bytes, which would desync the
length-prefixed strings inside the blob.
"""

from httpx import ASGITransport, AsyncClient

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from fobo.contracts.models import Caller, CandidateCause, AnalysisDraft, PatternGroup
from fobo.web.main import create_app

OLD_MODULE = "app.contracts.models"


def test_a_value_pickled_under_the_old_module_name_still_deserializes_typed(monkeypatch):
    monkeypatch.setattr(PatternGroup, "__module__", OLD_MODULE)
    serde = JsonPlusSerializer()

    group = PatternGroup(
        group_id="g1",
        pattern_code="P-204",
        label="FX timing lag",
        mode="auto",
        break_ids=["B-1", "B-2"],
    )
    typ, data = serde.dumps_typed(group)

    restored = serde.loads_typed((typ, data))

    assert isinstance(restored, PatternGroup), (
        f"expected a typed PatternGroup, got {type(restored)!r} — "
        "the app.contracts.models alias did not resolve"
    )
    assert restored.break_ids == ["B-1", "B-2"]


async def test_a_decision_on_a_pre_rename_checkpoint_still_succeeds(monkeypatch):
    """Reproduces sess-r-1055's shape: an investigation whose checkpoint was
    written while the contract models still named `app.contracts.models`,
    read back by today's code."""
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test", timeout=120
    ) as client:
        # Patch every contract type LangGraph will serialize while the
        # investigation runs, so the checkpoint it writes names the old
        # module — exactly what a pre-rename investigation left behind.
        for cls in (Caller, CandidateCause, AnalysisDraft, PatternGroup):
            monkeypatch.setattr(cls, "__module__", OLD_MODULE)

        # Opens R-1055's investigation and checkpoints its state under the
        # old module name.
        board = await client.get("/api/board")
        assert board.status_code == 200

        # Restore the module names — like today's process, which only ever
        # imports the new module — before anything reads the checkpoint back.
        monkeypatch.undo()

        r = await client.post(
            "/api/recs/R-1055/decisions",
            json={"ids": ["B-1", "B-2", "B-3", "B-4", "B-5", "B-6"], "decision": "Approved"},
            headers={"Idempotency-Key": "k-pre-rename"},
        )

    assert r.status_code == 201, r.text
    statuses = {a["id"]: a["status"] for a in r.json()["rec"]["adjustments"]}
    assert statuses["B-1"] == "Approved"
