"""The trusted SSO proxy, entitlement revocation, and case visibility filtered
in the database (with paging)."""

import dataclasses

from agent_one_finance import entitlement
from agent_one_finance.config import settings
from agent_one_finance.web import main
from tests.agent_one_finance.conftest import FOBO, RECON, VARIANCE


def _patch(monkeypatch, **changes):
    patched = dataclasses.replace(settings(), **changes)
    monkeypatch.setattr(main, "settings", lambda: patched)


async def _open(api, user, capability, key, group=None):
    res = await api.post(f"/api/capabilities/{capability}/cases",
                         json={"case_key": key, "team_group": group}, headers=api.as_user(user))
    assert res.status_code == 201, res.text
    return res.json()


async def test_with_a_proxy_secret_only_proxied_requests_get_in(api, monkeypatch):
    _patch(monkeypatch, trusted_proxy_secret="s3cret-from-the-proxy")
    direct = await api.get("/api/me", headers=api.as_user("bob"))
    assert direct.status_code == 401 and "trusted proxy" in direct.text
    wrong = await api.get("/api/me", headers={**api.as_user("bob"), "X-AOF-Proxy-Secret": "guess"})
    assert wrong.status_code == 401
    ok = await api.get("/api/me", headers={**api.as_user("bob"), "X-AOF-Proxy-Secret": "s3cret-from-the-proxy"})
    assert ok.status_code == 200
    assert (await api.get("/health")).status_code == 200          # health stays open for probes


async def test_the_entitlements_service_can_make_a_change_apply_now(api, monkeypatch):
    assert (await api.post("/api/entitlements/invalidate", json={})).status_code == 404   # off by default
    _patch(monkeypatch, entitlement_webhook_secret="hook-secret")
    await api.get("/api/me", headers=api.as_user("bob"))                  # cached now
    refused = await api.post("/api/entitlements/invalidate", json={"user_id": "bob"},
                             headers={"X-AOF-Webhook-Secret": "nope"})
    assert refused.status_code == 401
    ok = await api.post("/api/entitlements/invalidate", json={"user_id": "bob"},
                        headers={"X-AOF-Webhook-Secret": "hook-secret"})
    assert ok.json() == {"invalidated": 1}
    assert isinstance(entitlement.entitlements(), entitlement.CachedEntitlement)


async def test_cases_are_filtered_by_data_scope_in_the_database(api):
    await _open(api, "frank", RECON, {"book": "PRIME-MB-01", "cob": "2026-08-03"}, FOBO)
    await _open(api, "frank", RECON, {"book": "PRIME-MB-02", "cob": "2026-08-03"}, FOBO)
    frank = (await api.get(f"/api/capabilities/{RECON}/cases", headers=api.as_user("frank"))).json()
    gina = (await api.get(f"/api/capabilities/{RECON}/cases", headers=api.as_user("gina"))).json()
    assert len(frank) == 2
    assert [c["case_key"]["book"] for c in gina] == ["PRIME-MB-01"]      # her one book
    inbox = (await api.get("/api/inbox", headers=api.as_user("gina"))).json()
    assert {r["subject"] for r in inbox} == {"PRIME-MB-01 · COB 2026-08-03"}


async def test_case_lists_page(api):
    for period in ("2026-07", "2026-08", "2026-09"):
        await _open(api, "bob", VARIANCE, {"entity": "UK01", "period": period})
    url = f"/api/capabilities/{VARIANCE}/cases"
    first = (await api.get(url + "?limit=2", headers=api.as_user("bob"))).json()
    rest = (await api.get(url + "?limit=2&offset=2", headers=api.as_user("bob"))).json()
    assert len(first) == 2 and len(rest) == 1
    assert {c["case_id"] for c in first}.isdisjoint({c["case_id"] for c in rest})
