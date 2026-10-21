"""Build the demo tasks the console snapshot is recorded from, dated around a day you choose.

    python build-demo-tasks.py --today 2026-10-15 [--api http://localhost:8300] [--no-sim] [agent ...]
    python build-demo-tasks.py --today 2026-10-20 --examples

Run it against a dev stack whose database has the agents but no tasks (see README.md,
"To rebuild the snapshot"). Every task is opened, run and decided through the API the way
people would in the console: the previous business day's COB signed off this morning, today's
COB in progress (some at the tollgate, some waiting for review), month-end items for the
previous month. The FOBO skill's curated books exist only on their own COB, so those tasks
keep it. Name agents to build only those.

--examples builds the tasks the snapshot's walkthrough explains (src/snapshot/walkthrough.ts
in apps/web): MB Rec breaks for RATES-LDN-04 (the previous COB's task signed off, today's
waiting for Rita), and CATS vs MOTIF by FOBO group and region, opened the way FOBO's feed
opens them: one event per group, region and COB ("FOBO CSV loaded") for Rates and FI Credit
in EMEA, APAC and the Americas. By mid-morning in London Rates APAC and FI Credit APAC are
signed off, FI Credit EMEA has its static-data problem approved and the rest open, and Rates
EMEA (yesterday's signed off), Rates AMER and FI Credit AMER wait for review. The API must
take events: start it with AOF_EVENT_SECRET set, and pass the same value (--event-secret).
"""
import argparse
import datetime as dt
import json
import time
import urllib.error
import urllib.request
import uuid

API = "http://localhost:8300"
SIM = "2026-10-09"   # the COB of the FOBO skill's curated books (stub_connectors/fobo_simulation.py)
T = Y = MONTH = PREV_MONTH = ""


def business_day_before(day: dt.date) -> dt.date:
    day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def month_before(day: dt.date) -> str:
    return (day.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")


def call(method, path, user, body=None, headers=None):
    req = urllib.request.Request(API + path, method=method, headers={"X-AOF-User": user, "Content-Type": "application/json", **(headers or {})},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def settle(cid, user, seconds=240):
    for _ in range(seconds * 2):
        s, c = call("GET", f"/api/tasks/{cid}", user)
        if c["status"] not in ("running", "queued", "opening", "open"):
            return c
        time.sleep(0.5)
    return c


def decide_all(c, user):
    for g in c["groups"]:
        if g.get("decision"):
            continue
        f = g.get("finding") or {}
        fobo = "side" in f or "category" in f
        if fobo and not f.get("verdict"):
            action = "reject"
            comment = f"No verdict: the side is not proven. {f.get('escalate_to') or 'The owning team'} to confirm before any adjustment."
            answers = None
        else:
            action = "approve"
            comment = f"Agreed: {f['verdict']}." if f.get("verdict") else "Checked against the evidence; agreed."
            answers = [{"id": q["id"], "answer": "yes", "note": q.get("known") or None} for q in g.get("checklist") or []] or None
        s, out = call("POST", f"/api/tasks/{c['task_id']}/decisions", user, {
            "group_id": g["group_id"], "action": action, "comment": comment, "idempotency_key": f"d-{uuid.uuid4()}",
            "confirmed": True, "review_seconds": 60, "checklist": answers})
        if s not in (200, 201):
            print(f"      {g['label'][:40]}: {action} -> {s} {json.dumps(out)[:200]}")


def drive(cap, group, key, target, opener="aof-scheduler", decider="frank", publisher="rhea"):
    s, c = call("POST", f"/api/agents/{cap}/tasks", opener, {"task_key": key, "team_group": group})
    if s not in (200, 201):
        print(f"  ! {cap} {key}: open -> {s} {json.dumps(c)[:300]}")
        return None
    return work(c["task_id"], target, decider, publisher, key)


def work(cid, target, decider="frank", publisher="rhea", key=None):
    """Take an opened task as far as `target`: natural, tollgate, review, publish or done."""
    for _ in range(12):
        c = settle(cid, decider)
        st = c["status"]
        if target == "natural" or st in ("completed", "failed", "stopped", "escalated", "shadow"):
            break
        if st.startswith("paused_before_"):
            step = st[len("paused_before_"):]
            if target == "tollgate":
                break
            if step == "publish":
                if target != "done":
                    break
                s, out = call("POST", f"/api/tasks/{cid}/publish", publisher, {"idempotency_key": f"p-{uuid.uuid4()}"})
            elif step == "review":
                if target == "review":
                    break
                s, out = call("POST", f"/api/tasks/{cid}/gates/{step}", decider,
                              {"action": "continue", "idempotency_key": f"g-{uuid.uuid4()}"})
            else:
                s, out = call("POST", f"/api/tasks/{cid}/gates/{step}", decider, {
                    "action": "continue", "idempotency_key": f"g-{uuid.uuid4()}",
                    "comment": "Classification checked against MB Rec; books complete. Go ahead."})
            if s not in (200, 201):
                print(f"      gate {step} -> {s} {json.dumps(out)[:200]}")
                break
            continue
        if st == "awaiting_review":
            if target in ("review", "tollgate"):
                break
            decide_all(c, decider)
            continue
        if st == "awaiting_publish":
            if target != "done":
                break
            s, out = call("POST", f"/api/tasks/{cid}/publish", publisher, {"idempotency_key": f"p-{uuid.uuid4()}"})
            if s not in (200, 201):
                print(f"      publish -> {s} {json.dumps(out)[:200]}")
                break
            continue
        break
    c = settle(cid, decider)
    print(f"  {cid:<44} {json.dumps(key) if key else c['subject']:<60} {c['status']}")
    return cid


RECON, REGIONAL = "recon.investigation", "cats-vs-motif"
GROUPS = {"500081": "Rates", "500082": "FI Credit"}
EVENT_SECRET = "demo"


def event(group: str, region: str, cob: str) -> str | None:
    """FOBO's feed: its CSV for one group, region and COB has loaded."""
    s, out = call("POST", "/api/events", "aof-scheduler", {
        "agent_id": RECON, "team_group": REGIONAL, "event": "FOBO CSV loaded",
        "task_key": {"group": int(group), "group_name": GROUPS[group], "region": region, "cob": cob}},
        headers={"X-AOF-Event-Secret": EVENT_SECRET})
    if s not in (200, 201):
        print(f"  ! event {GROUPS[group]} {region} {cob}: {s} {json.dumps(out)[:300]}")
        return None
    return out["task_id"]


def approve(c: dict, user: str, label: str, comment: str) -> None:
    """Approve one proposal of a task, as its reviewer would from its Summary."""
    g = next(g for g in c["groups"] if g["label"] == label and not g.get("decision"))
    s, out = call("POST", f"/api/tasks/{c['task_id']}/decisions", user, {
        "group_id": g["group_id"], "action": "approve", "comment": comment, "confirmed": True,
        "idempotency_key": f"d-{uuid.uuid4()}", "review_seconds": 240})
    print(f"  {c['subject']}: {label} approved -> {s}")


def regional_day(today: str, yesterday: str) -> None:
    """One task per FOBO group, region and COB, each worked by its own controllers."""
    rates_emea_before = event("500081", "EMEA", yesterday)
    if rates_emea_before:
        work(rates_emea_before, "done", decider="rita")
    ids = {(g, r): event(g, r, today) for g in GROUPS for r in ("APAC", "EMEA", "AMER")}
    for (g, r), cid in ids.items():
        if cid:
            print(f"  {cid:<44} {GROUPS[g]} {r} {today}: {settle(cid, 'dana')['status']}")
    # APAC works first: Hana signs off Rates APAC, Mei FI Credit APAC.
    work(ids[("500081", "APAC")], "done", decider="hana")
    work(ids[("500082", "APAC")], "done", decider="mei")
    # EMEA: Lars approves the region's static-data problem, one decision for every book.
    fic_emea = settle(ids[("500082", "EMEA")], "lars")
    if any(g["label"] == "Data quality break · back office" for g in fic_emea["groups"]):
        approve(fic_emea, "lars", "Data quality break · back office",
                "EMEA: a new issue not yet set up in MOTIF static data, in every book of the product; "
                "Technology is setting it up. DO NOT POST.")


def main():
    global API, T, Y, MONTH, PREV_MONTH, EVENT_SECRET
    p = argparse.ArgumentParser()
    p.add_argument("--today", default=dt.date.today().isoformat(), help="the COB of today's tasks (default: today)")
    p.add_argument("--api", default=API)
    p.add_argument("--no-sim", action="store_true", help="leave out the FOBO skill's curated books (their COB is fixed)")
    p.add_argument("--examples", action="store_true", help="only the walkthrough's tasks: MB Rec breaks for one book, "
                   "and CATS vs MOTIF by FOBO group and region from FOBO's events")
    p.add_argument("--event-secret", default=EVENT_SECRET, help="the API's AOF_EVENT_SECRET, for FOBO's events")
    p.add_argument("only", nargs="*", help="agents to build (default: all)")
    a = p.parse_args()
    today = dt.date.fromisoformat(a.today)
    API, T, Y = a.api.rstrip("/"), today.isoformat(), business_day_before(today).isoformat()
    EVENT_SECRET = a.event_secret
    MONTH, PREV_MONTH = month_before(today), month_before(today.replace(day=1) - dt.timedelta(days=1))
    only = a.only
    if a.examples:
        for key, target in [({"book": "RATES-LDN-04", "cob": Y}, "done"), ({"book": "RATES-LDN-04", "cob": T}, "review")]:
            drive("break.investigation", "fobo-rates", key, target, decider="rita")
        regional_day(T, Y)
        return
    plan = []
    prime = [f"PRIME-MB-{n:02d}" for n in range(1, 7)]
    rates = ["RATES-LDN-01", "RATES-LDN-02", "RATES-LDN-03", "RATES-LDN-04"]
    # CATS vs MOTIF reconciliation: yesterday mostly signed off, today waiting for review.
    for b in prime:
        plan.append(("recon.investigation", "cats-motif", {"book": b, "cob": Y}, "done" if b <= "PRIME-MB-04" else "review", "frank"))
    for b in rates:
        plan.append(("recon.investigation", "cats-motif-rates", {"book": b, "cob": Y}, "done", "rita"))
    plan.append(("recon.investigation", "cash-bank-ledger", {"entity": "UK01", "date": Y}, "done", "erin"))
    for b in prime:
        plan.append(("recon.investigation", "cats-motif", {"book": b, "cob": T}, "review", "frank"))
    for b in rates:
        plan.append(("recon.investigation", "cats-motif-rates", {"book": b, "cob": T}, "review", "rita"))
    plan.append(("recon.investigation", "cash-bank-ledger", {"entity": "UK01", "date": T}, "review", "erin"))
    plan.append(("recon.investigation", "cash-bank-ledger", {"entity": "US01", "date": T}, "review", "erin"))
    # FOBO break investigation: yesterday signed off, today at the tollgate or in review.
    for b in ["PRIME-MB-01", "PRIME-MB-02", "PRIME-MB-03"]:
        plan.append(("break.investigation", "fobo-prime", {"book": b, "cob": Y}, "done", "frank"))
    for b, t in [("PRIME-MB-01", "tollgate"), ("PRIME-MB-02", "review"), ("PRIME-MB-03", "review"),
                 ("PRIME-MB-04", "tollgate"), ("PRIME-MB-06", "tollgate")]:
        plan.append(("break.investigation", "fobo-prime", {"book": b, "cob": T}, t, "frank"))
    plan.append(("break.investigation", "fobo-rates", {"book": "RATES-LDN-01", "cob": T}, "review", "rita"))
    if not a.no_sim:
        plan.append(("break.investigation", "fobo-prime", {"book": "PRIME-SIM-01", "cob": SIM}, "review", "frank"))
        plan.append(("break.investigation", "fobo-prime", {"book": "PRIME-SIM-02", "cob": SIM}, "tollgate", "frank"))
    # The FOBO skill as one model session.
    for b, cob in [*([] if a.no_sim else [("PRIME-SIM-01", SIM), ("PRIME-SIM-02", SIM)]), ("PRIME-MB-10", T), ("PRIME-MB-11", T)]:
        plan.append(("break.investigation.skill", None, {"book": b, "cob": cob}, "review", "frank"))
    # The guide's examples: price and position per book, and one task per named P&L.
    plan.append(("fobo.price.position", "prime", {"book": "PRIME-MB-01", "cob": Y}, "done", "frank"))
    plan.append(("fobo.price.position", "prime", {"book": "PRIME-MB-02", "cob": T}, "review", "frank"))
    plan.append(("fobo.named.pnl", "prime-financing", {"named_pnl": "PRIME-FINANCING-EMEA", "cob": Y}, "done", "frank"))
    plan.append(("fobo.named.pnl", "prime-financing", {"named_pnl": "PRIME-FINANCING-EMEA", "cob": T}, "review", "frank"))
    plan.append(("fobo.named.pnl", "prime-financing", {"named_pnl": "PRIME-FINANCING-US", "cob": T}, "tollgate", "frank"))
    # Other teams.
    plan.append(("payments.exceptions", None, {"entity": "UK01", "date": Y}, "done", "paula"))
    plan.append(("payments.exceptions", None, {"entity": "UK01", "date": T}, "review", "paula"))
    plan.append(("client.complaints", None, {"entity": "UK01", "date": T}, "natural", "carla"))
    plan.append(("controls.operating-test", None, {"entity": "UK01", "date": T}, "natural", "tess"))
    plan.append(("fin.accruals", None, {"entity": "UK01", "period": MONTH}, "review", "bob"))
    plan.append(("fin.accruals-review", None, {"entity": "UK01", "period": MONTH}, "done", "bob"))
    plan.append(("fin.variance-commentary", None, {"entity": "UK01", "period": PREV_MONTH}, "done", "bob"))
    plan.append(("fin.variance-commentary", None, {"entity": "UK01", "period": MONTH}, "publish", "bob"))
    plan.append(("fin.variance-commentary", None, {"entity": "US01", "period": MONTH}, "review", "bob"))
    plan.append(("report.validation", None, {"entity": "UK01", "period": MONTH, "report": f"mgmt-report-{MONTH}.xlsx"}, "done", "bob"))
    for cap, group, key, target, decider in plan:
        if only and cap not in only:
            continue
        opener = "alice" if cap in ("fin.accruals-review", "report.validation") else "aof-scheduler"
        drive(cap, group, key, target, opener=opener, decider=decider)
    # The eval sets: the model run again over signed-off tasks, compared with what people decided.
    for cap, user, body in [("break.investigation", "frank", {"team_group": "fobo-prime", "limit": 5}),
                            ("fin.variance-commentary", "carol", {"limit": 5})]:
        if not only or cap in only:
            s, out = call("POST", f"/api/agents/{cap}/evals", user, body)
            print(f"  eval {cap}: {s} {out.get('run_id') if isinstance(out, dict) else out}")


if __name__ == "__main__":
    main()
