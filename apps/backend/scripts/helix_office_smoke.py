"""Agent One Finance office smoke test: is this deployment wired to the office's services?

Run it once the office settings are in place (HELIX_LLM_ADAPTER=agent_sdk,
PHOENIX_COLLECTOR_ENDPOINT, HELIX_ENTITLEMENT_URL, real connector URLs…):

    cd apps/backend
    .venv/bin/python scripts/helix_office_smoke.py --user <a real user id>
    .venv/bin/python scripts/helix_office_smoke.py --user <id> \\
        --case recon.investigation --group cats-motif --key book=PRIME-MB-01 --key cob=2026-08-03

Checks, in order — each prints PASS / FAIL / SKIP and why:
  1. database      reachable, and its schema is at the latest migration
  2. entitlements  the user resolves, with roles and data scopes
  3. connectors    every onboarded connector answers list_tools
  4. llm           which adapter is configured (model, effort, budget)
  5. tracing       which backend is set up; Phoenix endpoint reachable
  6. case          (with --case) one real case end to end: run, findings, the
                   model's cost and turns, tool calls, and its Phoenix trace id

Exit status is non-zero when any check fails. Nothing here writes to a bank
system: a case stops at its review pause.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("HELIX_RUN_MODE", "inline")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

RESULTS: list[tuple[str, str, str]] = []


def report(check: str, status: str, detail: str) -> None:
    RESULTS.append((check, status, detail))
    print(f"[{status:4}] {check:12} {detail}")


async def check_database() -> bool:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from helix.db import engine

    try:
        async with engine.connect() as conn:
            current = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    except Exception as e:
        report("database", "FAIL", f"{type(e).__name__}: {e}")
        return False
    head = ScriptDirectory.from_config(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))).get_current_head()
    if current != head:
        report("database", "FAIL", f"schema at {current}, latest is {head}: run `alembic upgrade head`")
        return False
    report("database", "PASS", f"reachable, schema at {head}")
    return True


async def check_entitlements(user: str | None):
    from helix.config import settings
    from helix.entitlement import entitlements

    source = "url " + settings().entitlement_url if settings().entitlement_url else "dev stub (config/helix/dev-users.yaml)"
    if not user:
        report("entitlements", "SKIP", f"{source}; pass --user to resolve one")
        return None
    try:
        caller = await entitlements().get(user)
    except Exception as e:
        report("entitlements", "FAIL", f"{source}: {e}")
        return None
    report("entitlements", "PASS", f"{source}: {user} roles={sorted(caller.roles)} scopes={caller.as_dict()['data_scopes']}")
    return caller


async def check_connectors() -> bool:
    from helix.views import _connector_health

    ok = True
    for c in await _connector_health():
        good = c["status"] == "up" and c["tools_served"] >= 1
        ok &= good
        report("connectors", "PASS" if good else "FAIL",
               f"{c['id']} ({c['transport']}): {c['status']}, {c['tools_served']} tools served, "
               f"{c['tools_allowed']} allowed, {c['latency_ms']} ms" + (f" — {c['error']}" if c["error"] else ""))
    return ok


def check_llm() -> None:
    from helix.llm import llm

    adapter = llm()
    if adapter.name == "agent-sdk":
        from helix.llm_agent_sdk import describe
        report("llm", "PASS", f"Claude Agent SDK: {describe(adapter)}")
    else:
        report("llm", "SKIP" if adapter.name in ("stub", "none") else "PASS",
               f"adapter `{adapter.name}`" + (" — set HELIX_LLM_ADAPTER=agent_sdk in the office" if adapter.name in ("stub", "none") else ""))


async def check_tracing() -> None:
    from helix.config import settings
    from helix.observability import setup_tracing

    how = setup_tracing()
    endpoint = settings().phoenix_endpoint
    if not endpoint:
        report("tracing", "SKIP" if how == "none" else "PASS", how)
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(endpoint.rstrip("/"))
        report("tracing", "PASS" if res.status_code < 500 else "FAIL", f"{how}; endpoint answered {res.status_code}")
    except Exception as e:
        report("tracing", "FAIL", f"{how}; endpoint unreachable: {type(e).__name__}: {e}")


async def check_case(caller, capability: str, group: str | None, key: dict[str, str]) -> bool:
    from helix import capabilities, cases, groups, knowledge
    from helix.workflow import setup_checkpointer

    await setup_checkpointer()
    await capabilities.seed()
    await groups.seed()
    await knowledge.seed_reference()
    try:
        case_id = await cases.open_case(capability, key, caller, group)
        d = await cases.case_detail(case_id, caller)
    except Exception as e:
        report("case", "FAIL", f"{type(e).__name__}: {e}")
        return False
    good = d["status"] in ("awaiting_review", "awaiting_publish", "completed")
    report("case", "PASS" if good else "FAIL", f"{case_id}: {d['status']}" + (f" — {d['error']}" if d["error"] else ""))
    for g in d["groups"]:
        f = g["finding"] or {}
        usage = f.get("usage") or {}
        cost = f" cost ${usage['cost_usd']:.4f}, {usage.get('turns')} turns" if usage.get("cost_usd") is not None else ""
        print(f"         · {g['label']}: {f.get('status')} by {f.get('decided_by')}{cost}"
              + (f", verdict {f['verdict']}" if f.get("verdict") else ""))
    calls = d["tool_calls"]
    print(f"         · {len(calls)} tool calls ({sum(not c['allowed'] for c in calls)} refused); "
          f"trace {d['trace_id'] or 'not recorded (tracing off?)'}")
    return good


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--user")
    p.add_argument("--case", help="capability id to open one case of")
    p.add_argument("--group", help="its team group, when the capability has groups")
    p.add_argument("--key", action="append", default=[], help="case key field=value (repeat)")
    a = p.parse_args()

    if not await check_database():
        return 1
    caller = await check_entitlements(a.user)
    await check_connectors()
    check_llm()
    await check_tracing()
    if a.case:
        if caller is None:
            report("case", "FAIL", "needs --user (a real user who may open it)")
        else:
            await check_case(caller, a.case, a.group, dict(kv.split("=", 1) for kv in a.key))
    else:
        report("case", "SKIP", "pass --case/--key to run one case end to end")
    from helix.db import engine
    await engine.dispose()
    failed = [r for r in RESULTS if r[1] == "FAIL"]
    print(f"\n{len(failed)} check(s) failed" if failed else "\nall checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
