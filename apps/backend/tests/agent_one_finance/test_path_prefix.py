"""AOF_PATH_PREFIX: the API answers under /finance as well, with the same checks."""

import pytest

from agent_one_finance import config


@pytest.fixture
def prefixed(monkeypatch):
    monkeypatch.setenv("AOF_PATH_PREFIX", "/finance/")
    config.settings.cache_clear()
    yield
    monkeypatch.delenv("AOF_PATH_PREFIX")
    config.settings.cache_clear()


async def test_same_answers_with_and_without_the_prefix(api, prefixed):
    assert (await api.get("/finance/health")).status_code == 200
    assert (await api.get("/health")).status_code == 200
    plain = await api.get("/api/me", headers={"X-AOF-User": "frank"})
    under = await api.get("/finance/api/me", headers={"X-AOF-User": "frank"})
    assert under.status_code == plain.status_code == 200 and under.json() == plain.json()
    assert (await api.get("/financex/api/me", headers={"X-AOF-User": "frank"})).status_code == 404


async def test_the_trusted_proxy_check_applies_under_the_prefix(api, prefixed, monkeypatch):
    monkeypatch.setenv("AOF_TRUSTED_PROXY_SECRET", "s3cret")
    config.settings.cache_clear()
    assert (await api.get("/finance/api/me", headers={"X-AOF-User": "frank"})).status_code == 401
    ok = await api.get("/finance/api/me", headers={"X-AOF-User": "frank", config.settings().proxy_secret_header: "s3cret"})
    assert ok.status_code == 200
