"""Cases that open themselves: on a schedule, or when another system says so.

Schedule: a capability (or one team's group) sets `case.opens_on: schedule`,
a cron `case.schedule`, the keys each run opens (`case.schedule_keys`, with
date templates), and `case.opens_as`, the service user it runs as — an
account in the entitlements system, so a scheduled case is entitled exactly
as that account is. Opening is idempotent (one case per key), so a missed or
repeated tick never opens a case twice.

Event: with `case.events: true`, POST /api/events opens a case (e.g. "the
file for UK01 2026-09 has arrived"), authenticated by HELIX_EVENT_SECRET.

The loop runs inside the API (HELIX_SCHEDULER=on, the default when runs are
in the background). With several API instances, one runs each minute
(the first to record it in helix_scheduler_tick). Times are in HELIX_SCHEDULE_TZ (default UTC).
"""

import asyncio
import logging
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger("helix.scheduler")

_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]   # minute hour day month weekday (0 or 7 = Sunday)


class CronError(ValueError):
    pass


def _field(spec: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            if not s.isdigit() or int(s) < 1:
                raise CronError(f"bad step in {spec!r}")
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            x, y = part.split("-", 1)
            if not (x.isdigit() and y.isdigit()):
                raise CronError(f"bad range in {spec!r}")
            a, b = int(x), int(y)
        elif part.isdigit():
            a = b = int(part)
        else:
            raise CronError(f"cannot read {spec!r}")
        if a < lo or b > hi or a > b:
            raise CronError(f"{spec!r} is outside {lo}-{hi}")
        out |= set(range(a, b + 1, step))
    return out


def parse_cron(expr: str) -> list[set[int]]:
    parts = expr.split()
    if len(parts) != 5:
        raise CronError(f"{expr!r}: a schedule has five fields (minute hour day month weekday)")
    fields = [_field(p, lo, hi) for p, (lo, hi) in zip(parts, _RANGES)]
    fields[4] = {0 if d == 7 else d for d in fields[4]}
    return fields


def cron_matches(expr: str, at: datetime) -> bool:
    minute, hour, day, month, weekday = parse_cron(expr)
    return (at.minute in minute and at.hour in hour and at.day in day and at.month in month
            and (at.isoweekday() % 7) in weekday)


def next_run(expr: str, after: datetime, horizon_days: int = 62) -> datetime | None:
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(horizon_days * 24 * 60):
        if cron_matches(expr, t):
            return t
        t += timedelta(minutes=1)
    return None


def _prev_business_day(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def render_keys(templates: list[dict[str, str]], at: datetime) -> list[dict[str, str]]:
    d = at.date()
    first = d.replace(day=1)
    tokens = {"today": d.isoformat(), "yesterday": (d - timedelta(days=1)).isoformat(),
              "prev_business_day": _prev_business_day(d).isoformat(),
              "this_month": first.strftime("%Y-%m"),
              "prev_month": (first - timedelta(days=1)).strftime("%Y-%m")}
    return [{k: str(v).format(**tokens) for k, v in t.items()} for t in templates]


def tz() -> ZoneInfo:
    return ZoneInfo(os.getenv("HELIX_SCHEDULE_TZ") or "UTC")


async def scheduled() -> list[dict]:
    """Every schedule in force: capability (or group), cron, next run, keys."""
    from helix import capabilities
    from helix import groups as team_groups

    out = []
    now = datetime.now(tz())
    for _, base in await capabilities.all_active():
        targets = [(None, base)]
        groups = await team_groups.active_groups(base.id)
        if groups:
            targets = [(cfg.group, m) for _, cfg, m in groups]
        for group, m in targets:
            if m.case.opens_on == "schedule" and m.case.schedule:
                out.append({"capability_id": m.id, "team_group": group, "schedule": m.case.schedule,
                            "next_run": next_run(m.case.schedule, now), "opens_as": m.case.opens_as,
                            "keys": m.case.schedule_keys, "timezone": str(tz())})
    return out


async def tick(at: datetime | None = None) -> list[str]:
    """Open every case due this minute. Returns the case ids opened (or found)."""
    from helix import cases
    from helix.entitlement import entitlements

    at = (at or datetime.now(tz())).replace(second=0, microsecond=0)
    opened = []
    for s in await scheduled():
        if not cron_matches(s["schedule"], at):
            continue
        try:
            caller = await entitlements().get(s["opens_as"])
        except Exception as e:
            log.error("schedule %s/%s: cannot act as %s: %s", s["capability_id"], s["team_group"], s["opens_as"], e)
            continue
        for key in render_keys(s["keys"], at):
            try:
                opened.append(await cases.open_case(s["capability_id"], key, caller, s["team_group"]))
            except Exception as e:  # one bad key never stops the others
                log.error("schedule %s/%s: %s: %s", s["capability_id"], s["team_group"], key, e)
    return opened


async def _lead_this_minute(at: datetime) -> bool:
    """One instance runs each minute: whoever records it first."""
    from sqlalchemy.dialects.postgresql import insert

    from helix.db import get_session
    from helix.models import SchedulerTick

    async with get_session() as s:
        res = await s.execute(insert(SchedulerTick).values(minute=at.strftime("%Y-%m-%dT%H:%M"))
                              .on_conflict_do_nothing())
        await s.commit()
        return res.rowcount == 1


async def run_forever() -> None:
    while True:
        now = datetime.now(tz())
        await asyncio.sleep(60 - now.second + 0.5)
        at = datetime.now(tz()).replace(second=0, microsecond=0)
        try:
            if await _lead_this_minute(at):
                opened = await tick(at)
                if opened:
                    log.info("scheduler opened %d case(s)", len(opened))
                from helix import deadlines
                for case_id, kind in await deadlines.check(at):
                    log.info("deadline reminder %s for %s", kind, case_id)
                from helix import asks
                for request_id, kind in await asks.chase(at):
                    log.info("question %s %s", request_id, kind)
                from helix import timekeeping
                for case_id, kind in await timekeeping.check_waits(at):
                    log.info("case %s %s", case_id, kind)
                for case_id, clock, kind in await timekeeping.check_clocks(at):
                    log.info("case %s clock %s %s", case_id, clock, kind)
        except Exception:
            log.exception("scheduler tick failed")
