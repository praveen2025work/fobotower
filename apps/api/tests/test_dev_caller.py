"""A second dev caller, so a change drafted by one person can be approved by another."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.auth import DEV_CALLERS, current_caller, dev_caller_middleware
from api.main import create_app


def _probe_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(dev_caller_middleware)

    @app.get("/who")
    async def who() -> dict:
        c = current_caller()
        return {"id": c.staff_id, "roles": c.roles}

    return app


async def _who(headers=None):
    async with AsyncClient(transport=ASGITransport(app=_probe_app()),
                           base_url="http://test") as c:
        return await c.get("/who", headers=headers or {})


async def test_without_the_header_the_caller_is_the_stub(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    assert (await _who()).json()["id"] == "praveen"


async def test_in_dev_the_header_selects_another_caller(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    assert (await _who({"X-Dev-Caller": "asha"})).json() == {"id": "asha", "roles": ["PC"]}


async def test_outside_dev_the_header_is_ignored(monkeypatch):
    monkeypatch.delenv("FOBO_ENV", raising=False)
    assert (await _who({"X-Dev-Caller": "asha"})).json()["id"] == "praveen"


async def test_an_unknown_dev_caller_is_refused_with_the_valid_names(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    r = await _who({"X-Dev-Caller": "mallory"})
    assert r.status_code == 400
    assert "praveen" in r.json()["detail"] and "asha" in r.json()["detail"]


async def test_the_binding_does_not_leak_into_the_next_request(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    await _who({"X-Dev-Caller": "asha"})
    assert (await _who()).json()["id"] == "praveen"


def test_both_dev_callers_are_product_control():
    assert all("PC" in c.roles for c in DEV_CALLERS.values())


async def test_the_api_app_installs_the_switch(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test") as c:
        r = await c.get("/health", headers={"X-Dev-Caller": "mallory"})
    assert r.status_code == 400


async def test_the_board_names_the_caller_and_lists_dev_callers_only_in_dev(monkeypatch):
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test", timeout=120) as c:
        monkeypatch.setenv("FOBO_ENV", "dev")
        board = (await c.get("/api/helix/board", headers={"X-Dev-Caller": "asha"})).json()
        assert board["caller"]["id"] == "asha"
        assert [d["id"] for d in board["devCallers"]] == ["praveen", "asha"]
        monkeypatch.delenv("FOBO_ENV")
        assert "devCallers" not in (await c.get("/api/helix/board")).json()
