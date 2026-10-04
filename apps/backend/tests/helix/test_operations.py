"""The run-the-bank view: health, connectors, KPIs, fleet, incidents — scoped like every read."""

from helix import llm
from helix.llm import ReasonResult
from tests.helix.conftest import CASH, FOBO, RECON, VARIANCE


class Snooping:
    name = "snooping"

    async def reason(self, request, tools):
        try:
            await tools("ledger.postings", {"entity": "UK01", "date": "2026-09-30"})
        except Exception:
            pass
        return ReasonResult(status="escalated", reason="no evidence")


async def _ops(api, user):
    res = await api.get("/api/operations", headers=api.as_user(user))
    assert res.status_code == 200, res.text
    return res.json()


async def test_every_connector_is_probed(api):
    ops = await _ops(api, "frank")
    assert ops["health"]["database"] == "connected"
    by_id = {c["id"]: c for c in ops["connectors"]}
    assert {"cats", "motif", "gl", "bank"} <= set(by_id)
    assert all(c["status"] == "up" and c["tools_served"] >= 1 for c in by_id.values())


async def test_the_fleet_and_kpis_only_count_what_the_caller_may_see(api):
    await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("frank"),
                   json={"case_key": {"book": "PRIME-MB-01", "cob": "2026-08-03"}, "team_group": FOBO})
    await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("dan"),
                   json={"case_key": {"entity": "UK01", "date": "2026-10-02"}, "team_group": CASH})
    frank, dan = await _ops(api, "frank"), await _ops(api, "dan")
    assert [f["name"] for f in frank["fleet"]] == ["CATS vs MOTIF (FOBO)"]
    assert [f["name"] for f in dan["fleet"]] == ["Cash — bank vs ledger"]
    assert frank["kpi"]["runs24"] == 1 and frank["kpi"]["pendingApprovals"] == 1
    assert frank["fleet"][0]["href"] == f"/capabilities/{RECON}/groups/{FOBO}"
    assert len(frank["fleet"][0]["sparkline"]) == 24
    assert not any("cats." in line["message"] for line in dan["tail"])


async def test_refused_calls_become_an_incident(api):
    llm._adapter = Snooping()
    await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("alice"),
                   json={"case_key": {"entity": "UK01", "period": "2026-09"}})
    ops = await _ops(api, "alice")
    refused = [i for i in ops["incidents"] if i["title"] == "Refused calls to ledger.postings"]
    assert refused and refused[0]["count"] >= 1 and refused[0]["status"] == "degraded"
    assert any(line["level"] == "warn" for line in ops["tail"])
    assert ops["fleet"][0]["status"] == "degraded"                    # escalated groups
