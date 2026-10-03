"""Every Helix setting, read from the environment once.

The plug points for the office environment are here, all optional:

  HELIX_LLM_ADAPTER        none | stub | "module:attr" (your LLM connector)
  HELIX_TRACING_SETUP      "module:attr" called once at startup (e.g. Phoenix)
  PHOENIX_COLLECTOR_ENDPOINT  if set and arize-phoenix-otel is installed,
                           Helix registers Phoenix itself
  HELIX_ENTITLEMENT_URL    the central entitlements service; unset = dev stub
  HELIX_IDENTITY_HEADER    the header carrying the signed-in user (SSO proxy)
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class HelixSettings:
    database_url: str
    config_dir: Path
    llm_adapter: str
    tracing_setup: str | None
    phoenix_endpoint: str | None
    entitlement_url: str | None
    entitlement_ttl_seconds: int
    console_origin: str
    identity_header: str


@lru_cache
def settings() -> HelixSettings:
    env = os.getenv
    return HelixSettings(
        # Same database as the rest of the app unless told otherwise.
        database_url=env("HELIX_DATABASE_URL")
        or env("FOBO_DATABASE_URL")
        or "postgresql+asyncpg://fobo:fobo@localhost:5433/fobo",
        config_dir=Path(env("HELIX_CONFIG_DIR") or REPO_ROOT / "config" / "helix"),
        llm_adapter=env("HELIX_LLM_ADAPTER") or "stub",
        tracing_setup=env("HELIX_TRACING_SETUP") or None,
        phoenix_endpoint=env("PHOENIX_COLLECTOR_ENDPOINT") or None,
        entitlement_url=env("HELIX_ENTITLEMENT_URL") or None,
        entitlement_ttl_seconds=int(env("HELIX_ENTITLEMENT_TTL_SECONDS") or 300),
        console_origin=env("HELIX_CONSOLE_ORIGIN") or "http://localhost:3100",
        # Who is calling. In the office, the SSO proxy's header (e.g. X-Remote-User).
        identity_header=env("HELIX_IDENTITY_HEADER") or "X-Helix-User",
    )
