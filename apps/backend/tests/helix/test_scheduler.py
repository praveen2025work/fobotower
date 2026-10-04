"""Cases that open themselves: cron schedules with date-templated keys, run as
a service user; and events from other systems."""

import dataclasses
from datetime import datetime, timezone

import pytest

from helix import scheduler
from helix.capabilities import seed_files
from helix.config import settings
from helix.manifest import Manifest, problems
from helix.web import main
from tests.helix.conftest import FOBO, RECON, VARIANCE

UTC = timezone.utc


def test_cron_reads_five_fields_with_ranges_lists_and_steps():
    at = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)                    # Monday 2 Nov 07:00
    assert scheduler.cron_matches("0 7 2 * *", at)
    assert scheduler.cron_matches("*/15 6-8 * * 1-5", at)
    assert not scheduler.cron_matches("30 6 * * 1-5", at)
    assert scheduler.cron_matches("0 7 * * 0,1", at) and not scheduler.cron_matches("0 7 * * 6,7", at)
    assert scheduler.next_run("30 6 * * 1-5", at) == datetime(2026, 11, 3, 6, 30, tzinfo=UTC)
    for bad in ("0 7 * *", "61 * * * *", "a * * * *", "0 7 32 * *", "*/0 * * * *"):
        with pytest.raises(scheduler.CronError):
            scheduler.parse_cron(bad)


def test_keys_are_rendered_from_the_run_date():
    monday = datetime(2026, 11, 2, 6, 30, tzinfo=UTC)
    keys = scheduler.render_keys([{"book": "B1", "cob": "{prev_business_day}"},
                                  {"entity": "UK01", "period": "{prev_month}"}], monday)
    assert keys == [{"book": "B1", "cob": "2026-10-30"}, {"entity": "UK01", "period": "2026-10"}]


async def test_month_end_opens_last_months_lanes_as_the_service_user_once(api):
    at = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)
    first = await scheduler.tick(at)
    assert len(first) == 2
    cases = (await api.get(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("bob"))).json()
    assert {(c["case_key"]["entity"], c["case_key"]["period"], c["opened_by"]) for c in cases} == {
        ("UK01", "2026-10", "helix-scheduler"), ("US01", "2026-10", "helix-scheduler")}
    assert await scheduler.tick(at) == first                         # a repeated tick opens nothing new
    assert await scheduler.tick(datetime(2026, 11, 2, 7, 1, tzinfo=UTC)) == []   # not due


async def test_a_team_schedule_opens_each_book_for_the_previous_business_day(api):
    opened = await scheduler.tick(datetime(2026, 11, 2, 6, 30, tzinfo=UTC))
    assert len(opened) == 6
    cases = (await api.get(f"/api/capabilities/{RECON}/cases?team_group={FOBO}", headers=api.as_user("frank"))).json()
    assert {c["case_key"]["cob"] for c in cases} == {"2026-10-30"}


async def test_only_one_instance_runs_a_minute():
    at = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)
    assert await scheduler._lead_this_minute(at) is True
    assert await scheduler._lead_this_minute(at) is False


async def test_schedules_are_listed_with_their_next_run(api):
    rows = (await api.get("/api/schedules", headers=api.as_user("frank"))).json()
    assert [(r["capability_id"], r["team_group"]) for r in rows] == [(RECON, FOBO)]   # frank sees his group
    assert rows[0]["next_run"] and rows[0]["opens_as"] == "helix-scheduler"


async def test_events_open_a_case_when_enabled_and_allowed(api, monkeypatch):
    body = {"capability_id": RECON, "team_group": FOBO, "case_key": {"book": "PRIME-MB-02", "cob": "2026-10-30"},
            "event": "MOTIF EOD feed landed"}
    assert (await api.post("/api/events", json=body)).status_code == 404            # off by default
    monkeypatch.setattr(main, "settings", lambda: dataclasses.replace(settings(), event_secret="evt-secret"))
    assert (await api.post("/api/events", json=body, headers={"X-Helix-Event-Secret": "x"})).status_code == 401
    ok = await api.post("/api/events", json=body, headers={"X-Helix-Event-Secret": "evt-secret"})
    assert ok.status_code == 201 and ok.json()["opened_as"] == "helix-scheduler"
    no = await api.post("/api/events", headers={"X-Helix-Event-Secret": "evt-secret"},
                        json={"capability_id": VARIANCE, "case_key": {"entity": "UK01", "period": "2026-10"}})
    assert no.status_code == 403                                                       # variance takes no events


def test_a_schedule_needs_keys_and_a_service_user():
    m = next(m for m in seed_files() if m.id == VARIANCE).model_dump(by_alias=True)
    m["case"] = {**m["case"], "opens_as": None, "schedule_keys": [{"entity": "UK01"}], "schedule": "0 7 2 *"}
    found = problems(Manifest.model_validate(m))
    assert any("five fields" in p for p in found)
    assert any("misses period" in p for p in found)
    assert any("need a service user" in p for p in found)
