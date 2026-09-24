"""Run investigations end to end — deterministic, no LLM.

    .venv/bin/python scripts/run_investigation.py            every open rec
    .venv/bin/python scripts/run_investigation.py R-2048     one rec

Uses whatever FOBO_REASONER is set to. Unset means `none`: nothing calls a
model, and any break the playbook cannot settle escalates to a human. That
is the correct behaviour when no reasoner is available, and it shows exactly
how much of the run the playbook covers on its own.
"""

import asyncio
import os
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from api.main import create_app  # noqa: E402

OPEN_RECS = ["R-1055", "R-2031", "R-2048"]


def _line(char="─", n=78):
    return char * n


def _report(case: dict) -> None:
    h = case["header"]
    print(f"\n{_line('━')}\n{h['rec_id']}  {h['name']}  ·  {h['region']}  ·  COB {h['business_date']}")
    print(_line("━"))
    if case["state"] == "clear":
        print("  Nothing to review — no open breaks on this rec.")
        return

    findings = case.get("findings") or {}
    books = case.get("break_books") or {}
    deltas = case.get("deltas") or {}
    print(f"  {'BOOK':14} {'AMOUNT':>12}  {'HOW SETTLED':24} {'CAT':4} VERDICT")
    print(f"  {_line('-', 76)}")
    for bid, f in findings.items():
        how = f["rule_applied"] or f.get("pattern") or ("reasoner" if not f["deterministic"] else "?")
        how = f"rule {how}" if f["deterministic"] else f"→ {f.get('reasoner', 'none')}"
        amt = f"${deltas.get(bid, 0):,.2f}"
        flag = " *" if f.get("verdict_overridden") or f.get("requires_controller_confirmation") else ""
        print(f"  {books.get(bid, bid):14} {amt:>12}  {how:24} {f['category_code']:4} {f['verdict']}{flag}")

    notes = {(tuple(f.get("guard_reasons") or []), tuple(f.get("conditional_on") or []))
             for f in findings.values() if f.get("guard_reasons")}
    if notes:
        print("\n  * guard notes:")
        for reasons, cond in sorted(notes):
            for r in reasons:
                print(f"      {r}")
            if cond:
                print(f"      unset: {', '.join(cond)}")

    d = case.get("determinism") or {}
    if d:
        share = d.get("share")
        print(f"\n  Settled by the playbook, no LLM:  {d['deterministic']} of {d['total']}"
              f"  ({share:.0%})" if share is not None else "")
        if d.get("escalated_to_reasoner"):
            print(f"  Needed judgement:                 {d['escalated_to_reasoner']}"
                  f"  → escalated (reasoner: {os.getenv('FOBO_REASONER', 'none')})")
        if d.get("by_pattern"):
            print(f"  By pattern:                       "
                  + ", ".join(f"{k} {v}" for k, v in d["by_pattern"].items()))
    fv = next(iter(findings.values()), {}).get("playbook_version")
    if fv:
        print(f"  Playbook version:                 {fv}")


async def main(recs: list[str]) -> None:
    print(f"Reasoner: {os.getenv('FOBO_REASONER', 'none')}  (none = no LLM is called)")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://local",
                           timeout=180) as client:
        for rec in recs:
            r = await client.get(f"/api/recs/{rec}")
            if r.status_code != 200:
                print(f"\n{rec}: HTTP {r.status_code} — {r.text[:200]}")
                continue
            _report(r.json())
    print()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or OPEN_RECS))
