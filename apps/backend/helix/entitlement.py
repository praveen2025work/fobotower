"""Who a caller is, what they may do, and which data they may see.

Agent One Finance holds no roles. In the office, HELIX_ENTITLEMENT_URL points at the
central entitlements service and `HttpEntitlement` asks it:

  GET {url}/users/{user_id}/entitlements?app=helix
  -> {"roles": [...], "data_scopes": {"entity": ["UK01", ...], ...}}

If the bank's API has a different shape, supply your own adapter with
HELIX_ENTITLEMENT_ADAPTER="module:attr" (an object with `async get(user_id)`).

Unset, `StubEntitlement` reads config/helix/dev-users.yaml so the skeleton
runs with no bank connectivity. Either way: unknown user or service down
fails closed (`EntitlementError`), and a data scope of "*" means all.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import yaml

from helix import plugins
from helix.config import settings


class EntitlementError(RuntimeError):
    pass


@dataclass(frozen=True)
class Caller:
    user_id: str
    roles: frozenset[str]
    data_scopes: dict[str, frozenset[str]] = field(default_factory=dict)

    def has_any_role(self, roles) -> bool:
        return bool(self.roles & set(roles))

    def may_see(self, scope: str, value) -> bool:
        allowed = self.data_scopes.get(scope)
        if allowed is None:
            return False
        return "*" in allowed or str(value) in allowed

    def as_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "roles": sorted(self.roles),
            "data_scopes": {k: sorted(v) for k, v in self.data_scopes.items()},
        }


def _caller(user_id: str, body: dict) -> Caller:
    return Caller(
        user_id=user_id,
        roles=frozenset(body.get("roles", [])),
        data_scopes={k: frozenset(map(str, v)) for k, v in body.get("data_scopes", {}).items()},
    )


class EntitlementSource(Protocol):
    async def get(self, user_id: str) -> Caller: ...


class StubEntitlement:
    """Fixture users for development and tests."""

    def __init__(self, path=None):
        self.path = path or settings().config_dir / "dev-users.yaml"

    def users(self) -> dict[str, dict]:
        return (yaml.safe_load(self.path.read_text()) or {}).get("users", {})

    async def get(self, user_id: str) -> Caller:
        body = self.users().get(user_id)
        if body is None:
            raise EntitlementError(f"unknown user {user_id!r}")
        return _caller(user_id, body)


class HttpEntitlement:
    def __init__(self, url: str, timeout: float = 5.0, transport: httpx.AsyncBaseTransport | None = None):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.transport = transport  # tests inject a mock transport

    async def get(self, user_id: str) -> Caller:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                res = await client.get(
                    f"{self.url}/users/{user_id}/entitlements", params={"app": "helix"}
                )
        except httpx.HTTPError as e:
            raise EntitlementError(f"entitlement service unavailable: {e}") from e
        if res.status_code != 200:
            raise EntitlementError(f"entitlement service refused {user_id!r}: {res.status_code}")
        try:
            return _caller(user_id, res.json())
        except (ValueError, AttributeError, TypeError) as e:
            raise EntitlementError(f"entitlement service answered unreadably: {e}") from e


class CachedEntitlement:
    def __init__(self, source: EntitlementSource, ttl_seconds: int):
        self.source = source
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[float, Caller]] = {}

    async def get(self, user_id: str) -> Caller:
        hit = self._cache.get(user_id)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        caller = await self.source.get(user_id)
        self._cache[user_id] = (time.monotonic(), caller)
        return caller

    def invalidate(self, user_id: str | None = None) -> int:
        """Forget one user's cached entitlements (or everyone's); the next
        request asks the source again. Returns how many were dropped."""
        if user_id is None:
            n = len(self._cache)
            self._cache.clear()
            return n
        return 1 if self._cache.pop(user_id, None) else 0


_source: EntitlementSource | None = None


def entitlements() -> EntitlementSource:
    global _source
    if _source is None:
        s = settings()
        custom = os.getenv("HELIX_ENTITLEMENT_ADAPTER")
        if custom:
            source = plugins.load(custom)
        elif s.entitlement_url:
            source = HttpEntitlement(s.entitlement_url)
        else:
            source = StubEntitlement()
        _source = CachedEntitlement(source, s.entitlement_ttl_seconds)
    return _source
