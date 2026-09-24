"""MCP calls as the Helix session shows them, and the tools chat can run.

Every call shown is a source_call row: what was asked, what came back, and
how long it took. Chat answers run their own retrievals through the same
recorder, so a question asked in the session leaves the same audit trail as
the investigation itself.

Only tools the orchestrator can actually serve are here. FAS and custody are
not connected yet, so there is no posting preview or statement lookup rather
than an invented one.
"""

import time

from sqlalchemy import select

from app.db.models_ops import SourceCall
from app.grounding.recorder import GroundingRecorder, calls_for
from app.helix.fmt import money

# Row fields that hold an amount, formatted in the rec's currency for display.
MONEY_KEYS = {"delta", "amount", "figure", "source", "value", "pendingValue"}


def _display_row(row: dict, ccy: str) -> dict:
    out = {}
    for key, value in row.items():
        if key in MONEY_KEYS and isinstance(value, (int, float)):
            out[key] = money(value, ccy)
        elif value is None:
            out[key] = "not found" if key == "source" else "—"
        else:
            out[key] = value
    return out


def helix_call(call: dict, ccy: str) -> dict:
    """A recorded source_call, shaped for the session panel and inspector."""
    server, _, tool = call["tool"].partition(".")
    return {
        "id": call["call_id"],
        "server": server,
        "tool": tool,
        "args": call["params"],
        "rows": [_display_row(r, ccy) for r in call.get("rows") or []],
        "summary": call["summary"],
        "ms": call["latency_ms"],
        "status": "error" if call["error"] else "ok",
        "error": call["error"],
    }


async def session_calls(s, session_id: str, ccy: str) -> list[dict]:
    return [helix_call(c, ccy) for c in await calls_for(s, session_id)]


async def calls_by_id(s, ids: list[str], ccy: str) -> list[dict]:
    if not ids:
        return []
    rows = {c["call_id"]: c for c in await _calls(s, ids)}
    return [helix_call(rows[i], ccy) for i in ids if i in rows]


async def _calls(s, ids: list[str]) -> list[dict]:
    found = (await s.scalars(select(SourceCall).where(SourceCall.call_id.in_(ids)))).all()
    return [
        {
            "call_id": r.call_id, "tool": r.tool_name, "params": r.validated_parameters,
            "rows": r.result_rows, "summary": r.result_summary,
            "latency_ms": r.latency_ms, "error": r.error_detail,
        }
        for r in found
    ]


class SessionTools:
    """The retrievals a chat answer can make, each recorded as it runs."""

    def __init__(self, s, session_id: str, workspace: dict):
        self._s = s
        self._recorder = GroundingRecorder(s, session_id)
        self._session_id = session_id
        self._workspace = workspace
        self.call_ids: list[str] = []

    async def _record(self, application: str, tool: str, params: dict,
                      rows: list[dict], summary: str, started: float) -> None:
        self.call_ids.append(await self._recorder.record(
            application=application, tool=tool, params=params,
            row_count=len(rows), summary=summary, rows=rows,
            latency_ms=round((time.perf_counter() - started) * 1000),
        ))

    async def breaks(self, adjs: list[dict]) -> None:
        started = time.perf_counter()
        rows = [
            {"breakId": a["id"], "masterBook": a["book"], "pattern": a["pattern"],
             "delta": a["delta"], "type": a["type"], "ageSessions": a["agedSessions"]}
            for a in adjs
        ]
        await self._record(
            "MBRec", "mbrec.get_breaks", self._workspace,
            rows, f"{len(rows)} breaks", started,
        )

    async def break_legs(self, adjs: list[dict], **extra) -> None:
        started = time.perf_counter()
        rows = []
        for a in adjs:
            for side, key in (("CATS", "cats"), ("MOTIF", "motif")):
                for leg in a["legs"][key]:
                    rows.append({"breakId": a["id"], "masterBook": a["book"],
                                 "leg": side, "amount": leg["amount"]})
        await self._record(
            "MBRec", "mbrec.get_break_legs",
            self._workspace | {"breakIds": [a["id"] for a in adjs]} | extra,
            rows, f"{len(rows)} leg entries", started,
        )

    async def grounding(self, adjs: list[dict]) -> None:
        started = time.perf_counter()
        rows = [
            {"adjId": a["id"], "figure": a["delta"],
             "source": a["delta"] if a["grounded"] else None,
             "result": "Traced" if a["grounded"] else "Not traced"}
            for a in adjs
        ]
        failed = sum(1 for a in adjs if not a["grounded"])
        await self._record(
            "Helix", "helix.grounding_check",
            {"sessionId": self._session_id, "adjIds": [a["id"] for a in adjs]},
            rows, f"{len(adjs) - failed}/{len(adjs)} figures traced", started,
        )

    async def session_state(self, rows: list[dict]) -> None:
        started = time.perf_counter()
        await self._record(
            "Helix", "helix.get_session_state", {"sessionId": self._session_id},
            rows, f"{len(rows)} patterns", started,
        )
