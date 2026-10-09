"""Set up the example capability for real, step by step, through the AOF API.

    python setup_example.py --api http://localhost:8300
    python setup_example.py --api https://<aof internal address> --proxy-secret "$AOF_TRUSTED_PROXY_SECRET"

It does what people do in the console, in order, as the right person each time:

  1. frank (owner)        submits capability.yaml          -> version 1, a draft
  2. frank                tries to approve his own draft   -> refused: four eyes
  3. gina (second owner)  approves it                       -> the capability is live
  4. frank                submits group.yaml (Prime books)  -> a draft
  5. gina                 approves the group                -> the group is live
  6. the scheduler        opens a case for one book and COB (here by hand; an MB Rec event can do it)
  7. the run              load -> enrich -> classify -> group, then waits at the tollgate before `reason`
  8. frank (controller)   checks the classification and lets the run go on
  9. the run              reason -> draft -> validate, then waits for review
 10. frank                signs off each group with the checklist   -> recorded

Only the Python standard library and PyYAML. Re-running it skips what already exists.

To look at the case in the console on the way, stop and carry on later:
    python setup_example.py --until tollgate        # stops at the tollgate (prints the case id)
    python setup_example.py --case <id> --until review
    python setup_example.py --case <id>             # signs off and records
Reads capability.yaml and group.yaml from this folder, or from `--dir`. The named P&L
variant (one case for several master books) is in named-pnl/:
    python setup_example.py --dir named-pnl --key named_pnl=PRIME-FINANCING-EMEA --cob 2026-10-08
`--record out.json` saves every request and answer (the walkthrough in README.md was
written from one).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
LOG: list[dict] = []


class Api:
    def __init__(self, base: str, proxy_secret: str | None):
        self.base, self.proxy_secret = base.rstrip("/"), proxy_secret

    def call(self, method: str, path: str, user: str, body: dict | None = None) -> tuple[int, dict | list]:
        headers = {"X-AOF-User": user, "Content-Type": "application/json"}
        if self.proxy_secret:
            headers["X-AOF-Proxy-Secret"] = self.proxy_secret
        req = urllib.request.Request(self.base + path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                status, out = r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            status, out = e.code, json.loads(e.read() or b"null")
        LOG.append({"method": method, "path": path, "user": user, "body": body, "status": status, "answer": out})
        return status, out


def say(n: str, who: str, text: str) -> None:
    print(f"\n[{n}] {who}: {text}")


def must(status: int, out, ok=(200, 201)):
    if status not in ok:
        sys.exit(f"    failed: HTTP {status} {json.dumps(out)[:600]}")
    return out


def wait(api: Api, case_id: str, user: str, until, seconds: int = 120) -> dict:
    for _ in range(seconds * 2):
        _, case = api.call("GET", f"/api/cases/{case_id}", user)
        if until(case["status"]):
            return case
        if case["status"] in ("failed", "stopped"):
            sys.exit(f"    the run {case['status']}: {case.get('error')}")
        time.sleep(0.5)
    sys.exit(f"    still {case['status']} after {seconds}s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8300")
    p.add_argument("--proxy-secret")
    p.add_argument("--maker", default="frank")
    p.add_argument("--checker", default="gina")
    p.add_argument("--opener", default="aof-scheduler")
    p.add_argument("--dir", default=".", help="the folder with capability.yaml and group.yaml, e.g. named-pnl")
    p.add_argument("--book", default="PRIME-MB-01")
    p.add_argument("--cob", default="2026-10-01")
    p.add_argument("--key", action="append", default=[], metavar="FIELD=VALUE",
                   help="another case-key value, e.g. named_pnl=PRIME-FINANCING-EMEA")
    p.add_argument("--note", default="Breaks match MB Rec for the book. Desk says the IRS 5Y was re-marked "
                                     "on the 03:00 curve.", help="what the controller writes at the tollgate")
    p.add_argument("--until", choices=["tollgate", "review", "done"], default="done")
    p.add_argument("--case", help="carry on with this case instead of opening a new one")
    p.add_argument("--record")
    a = p.parse_args()
    api = Api(a.api, a.proxy_secret)

    folder = HERE / a.dir
    cap_text = (folder / "capability.yaml").read_text()
    cap = yaml.safe_load(cap_text)
    grp = yaml.safe_load((folder / "group.yaml").read_text())
    cid, gid = cap["id"], grp["group"]
    given = {"book": a.book, "cob": a.cob, **dict(k.split("=", 1) for k in a.key)}
    missing = [f for f in cap["case"]["key"] if f not in given]
    if missing:
        sys.exit(f"give the case key: --key {missing[0]}=<value>")
    case_key = {f: given[f] for f in cap["case"]["key"]}
    what = " COB ".join(case_key[f] for f in cap["case"]["key"])

    _, me = api.call("GET", "/api/me", a.maker)
    print(f"Signed in as {a.maker}: roles {me.get('roles')}; model adapter: {me.get('llm')}")

    # 1-3. The capability: submit, four eyes, approve.
    live = {c["id"]: c for c in must(*api.call("GET", "/api/capabilities", a.maker))}
    if cid in live:
        say("1-3", "capability", f"{cid} is already live (version {live[cid]['version']}); skipping")
    else:
        say("1", a.maker, f"submits capability.yaml ({len(cap['steps'])} steps: {', '.join(cap['steps'])})")
        out = must(*api.call("POST", "/api/authoring/submit", a.maker,
                             {"yaml": cap_text, "note": f"Example: {cap['name']}"}))
        version = out["version"]
        print(f"    stored as {cid} version {version}, status draft")

        say("2", a.maker, "tries to approve his own draft")
        status, out = api.call("POST", f"/api/capabilities/{cid}/versions/{version}/approve", a.maker)
        print(f"    HTTP {status}: {out.get('detail') if isinstance(out, dict) else out}")

        say("3", a.checker, "approves it")
        must(*api.call("POST", f"/api/capabilities/{cid}/versions/{version}/approve", a.checker))
        print(f"    {cid} version {version} is live")

    # 4-5. The team group: check, submit, approve.
    groups = must(*api.call("GET", f"/api/capabilities/{cid}/groups", a.maker))
    if any(g["group"] == gid for g in groups):
        say("4-5", "group", f"{gid} is already live; skipping")
    else:
        say("4", a.maker, f"checks group.yaml ({gid}) against the live capability, then submits it")
        found = must(*api.call("POST", f"/api/capabilities/{cid}/check", a.maker, {"config": grp}))
        print(f"    check: {'passes every platform check' if found['ok'] else found['problems']}")
        out = must(*api.call("POST", f"/api/capabilities/{cid}/groups", a.maker,
                             {"config": grp, "note": f"{grp['name']}: checks, tests, verdicts"}))
        gversion = out["version"]
        print(f"    stored as group {gid} version {gversion}, status draft")

        say("5", a.checker, "approves the group")
        must(*api.call("POST", f"/api/capabilities/{cid}/groups/{gid}/versions/{gversion}/approve", a.checker))
        print(f"    group {gid} version {gversion} is live")

    # 6-7. A case: opens, runs to the tollgate.
    if a.case:
        case_id = a.case
    else:
        say("6", a.opener, f"opens a case for {what} (here by hand; an MB Rec event can do it instead)")
        case = must(*api.call("POST", f"/api/capabilities/{cid}/cases", a.opener,
                              {"case_key": case_key, "team_group": gid}))
        case_id = case["case_id"]
        print(f"    case {case_id}: {case['subject']}")
        if case["status"] in ("completed", "failed", "stopped"):
            # One case per key: opening the same key again returns the case that exists.
            print(f"    {what} already has a case ({case['status']}); AOF returns it rather than "
                  "opening a second. Use another --cob, or Re-run it in the console.")
            return stop(a, case_id, case["status"])

    case = wait(api, case_id, a.maker, lambda s: s != "running")
    say("7", "the run", f"load, enrich, classify, group done; status {case['status']}")
    for call in case["tool_calls"]:
        print(f"    MCP tool {call['tool']}({', '.join(f'{k}={v}' for k, v in call['arguments'].items())})"
              f" -> {call['row_count']} rows, {call['latency_ms']} ms")
    for ds in case.get("datasets") or []:
        print(f"    data set {ds['name']} ({ds['row_count']} rows):")
        for r in ds["rows"][:10]:
            print("        " + ", ".join(f"{k} {v}" for k, v in r.items()))
    for it in case["items"]:
        failed = [t["id"] for t in it.get("tests") or [] if t["status"] == "fail"]
        not_run = [t["id"] for t in it.get("tests") or [] if t["status"] == "not_run"]
        where = f"{it['book']:<12} {it['instrument']:<11}" if "book" not in case_key else f"{it['item_id']:<11}"
        print(f"    {where} {it['difference']:>12,.2f}  {it.get('category')}/{it.get('side')}"
              f"  {it.get('cause_reason') or ''}"
              + (f"  tests failed: {failed}" if failed else "") + (f"  not run: {not_run}" if not_run else ""))

    if a.until == "tollgate":
        return stop(a, case_id, "at the tollgate")

    # 8. The tollgate.
    if case["status"] == "paused_before_reason":
        say("8", a.maker, "checks the breaks and the classification at the tollgate, and lets the run go on")
        must(*api.call("POST", f"/api/cases/{case_id}/gates/reason", a.maker,
                       {"action": "continue", "idempotency_key": f"gate-{uuid.uuid4()}",
                        "comment": a.note}))

    # 9. Reason, draft, validate.
    case = wait(api, case_id, a.maker, lambda s: s == "awaiting_review")
    say("9", "the run", "reason, draft and validate done; waiting for the controller")
    for g in case["groups"]:
        f = g["finding"] or {}
        print(f"    {g['label']:<40} items {', '.join(g['item_ids'])}")
        print(f"        verdict {f.get('verdict')}  status {f.get('status')}  decided by {f.get('decided_by')}"
              + (f"  guard: {f['guard']}" if f.get("guard") else "")
              + ("  model investigated" if f.get("sme_review") else ""))
        print(f"        {f.get('comment')}")

    if a.until == "review":
        return stop(a, case_id, "waiting for review")

    # 10. Review and record. A group with a verdict is approved; one without (the
    # model could not prove the side) is rejected with the reason, which is recorded.
    say("10", a.maker, "signs off each group with the checklist")
    for g in case["groups"]:
        f = g["finding"] or {}
        if g["decision"]:
            continue
        if f.get("verdict"):
            # The console shows what AOF already knows next to each question; the controller confirms it.
            answers = [{"id": q["id"], "answer": "yes", "note": q["known"] or None} for q in g["checklist"] or []]
            action, comment = "approve", f"Agreed: {f['verdict']}."
        else:
            answers = None
            action = "reject"
            owner = f.get("escalate_to") or "The owning team"
            comment = (f"No verdict: the side is not proven. {owner} to confirm which curve is right before "
                       "any adjustment." if f.get("category") == "A" else
                       f"No verdict: the side is not proven. {owner} to confirm before any adjustment.")
        status, out = api.call("POST", f"/api/cases/{case_id}/decisions", a.maker, {
            "group_id": g["group_id"], "action": action, "comment": comment,
            "idempotency_key": f"decide-{uuid.uuid4()}", "confirmed": bool(f.get("requires_confirmation")),
            "review_seconds": 45, "checklist": answers})
        print(f"    {g['label']:<40} {action} -> HTTP {status}"
              + ("" if status in (200, 201) else f" {json.dumps(out)[:300]}"))

    case = wait(api, case_id, a.maker, lambda s: s not in ("awaiting_review", "running"))
    stop(a, case_id, f"{case['status']} ({case.get('outcome')})")


def stop(a, case_id: str, where: str) -> None:
    print(f"\nCase {case_id}: {where}.")
    print(f"Open it in the console: /finance/cases/{case_id}")
    if where in ("at the tollgate", "waiting for review"):
        print(f"Carry on: python {Path(__file__).name}" + (f" --dir {a.dir}" if a.dir != "." else "")
              + f" --case {case_id}"
              + (" --until review" if a.until == "tollgate" else ""))
    if a.record:
        Path(a.record).write_text(json.dumps({"case_id": case_id, "log": LOG}, indent=1, default=str))
        print(f"Every request and answer: {a.record}")


if __name__ == "__main__":
    main()
