"""The console origin is configurable, so an e2e console can run beside the dev one."""

from httpx import ASGITransport, AsyncClient

from api.main import create_app


async def _preflight(origin: str):
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        return await c.options("/health", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET"})


async def test_the_dev_console_is_allowed_by_default(monkeypatch):
    monkeypatch.delenv("FOBO_CONSOLE_ORIGINS", raising=False)
    r = await _preflight("http://localhost:3100")
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3100"


async def test_extra_origins_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("FOBO_CONSOLE_ORIGINS", "http://localhost:3100, http://localhost:3101")
    r = await _preflight("http://localhost:3101")
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3101"
