"""Run investigations end to end — deterministic, no LLM.

    .venv/bin/python scripts/run_investigation.py            every open rec
    .venv/bin/python scripts/run_investigation.py R-2048     one rec

Uses whatever FOBO_REASONER is set to. Unset means `none`: nothing calls a
model, and any break the playbook cannot settle escalates to a human. That
is the correct behaviour when no reasoner is available, and it shows exactly
how much of the run the playbook covers on its own.

Starts each run through POST /api/recs/{id}/investigate — the classic
GET /api/recs/{id} this used to call is gone, replaced by the console's own
rec view at that URL and this dedicated investigate endpoint (spec §5). The
per-break findings table that route used to return is not in either
endpoint's response, so the report below reads the LangGraph step trace
instead (GET /api/recs/{id}/trace, unchanged) — the same steps a controller
sees in the console's "Graph run" panel.
"""

import asyncio
import os
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from fobo.web.dependencies import setup_checkpointer  # noqa: E402
from fobo.web.main import create_app  # noqa: E402

OPEN_RECS = ["R-1055", "R-2031", "R-2048"]

STATUS_MARK = {"done": "done", "waiting": "waiting", "skipped": "skipped", "pending": "pending"}


def _line(char="─", n=78):
    return char * n


def _report(header: dict, investigated: dict, trace: dict) -> None:
    print(f"\n{_line('━')}\n{header['rec_id']}  {header['name']}  ·  {header['region']}  "
          f"·  COB {header['business_date']}")
    print(_line("━"))
    print(f"  Status: {investigated['status']:16}  Workflow v{investigated['workflow_version']}"
          f"   Session {investigated['session_id']}")
    print(f"  {_line('-', 76)}")
    for step in trace["steps"]:
        mark = STATUS_MARK.get(step["status"], step["status"])
        print(f"  {step['label']:28} {mark:8} {step.get('summary', '')}")


async def main(recs: list[str]) -> None:
    print(f"Reasoner: {os.getenv('FOBO_REASONER', 'none')}  (none = no LLM is called)")
    # ASGITransport never runs the app's lifespan, so setup_checkpointer()
    # would otherwise never run — and running it lazily inside the first
    # request deadlocks on a fresh database (see fobo/web/dependencies.py::setup_checkpointer).
    await setup_checkpointer()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local",
                           timeout=180) as client:
        for rec in recs:
            r = await client.post(f"/api/recs/{rec}/investigate")
            if r.status_code == 409:
                print(f"\n{rec}: nothing to review — no open breaks on this rec.")
                continue
            if r.status_code != 200:
                print(f"\n{rec}: HTTP {r.status_code} — {r.text[:200]}")
                continue
            investigated = r.json()
            trace_body = (await client.get(f"/api/recs/{rec}/trace")).json()
            _report(trace_body["header"], investigated, trace_body["trace"])
    print()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or OPEN_RECS))
