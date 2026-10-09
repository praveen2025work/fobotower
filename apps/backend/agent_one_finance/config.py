"""Every Agent One Finance setting, read from the environment once.

The plug points for the office environment are here, all optional:

  AOF_PATH_PREFIX        also serve the API under this path (e.g. /finance), for a load
                           balancer that routes /finance/* here without rewriting paths
  AOF_DATABASE_URL       the database; or its parts, AOF_DATABASE_HOST, _PORT (5432), _NAME,
                           _USER and _PASSWORD (each can come from a secrets store key)
  AOF_LLM_ADAPTER        none | stub | "module:attr" (your LLM connector)
  AOF_TRACING_SETUP      "module:attr" called once at startup (e.g. Phoenix)
  PHOENIX_COLLECTOR_ENDPOINT  if set and arize-phoenix-otel is installed,
                           Agent One Finance registers Phoenix itself
  AOF_ENTITLEMENT_URL    the central entitlements service; unset = dev stub
  AOF_IDENTITY_HEADER    the header carrying the signed-in user (SSO proxy)
  AOF_TRUSTED_PROXY_SECRET  a secret the SSO proxy adds to every request;
                           set it and requests without it are refused
  AOF_ENTITLEMENT_WEBHOOK_SECRET  enables POST /api/entitlements/invalidate
  AOF_ENTITLEMENT_TTL_SECONDS     how long entitlements are cached (60)
  AOF_RUN_MODE           background (default) | inline — where case runs happen
  AOF_SCHEDULER          on | off — the schedule loop (on when runs are in the background)
  AOF_SCHEDULE_TZ        the time zone schedules are read in (UTC)
  AOF_EVENT_SECRET       enables POST /api/events (other systems open cases)
  AOF_ADMIN_ROLE         platform support role: switches connectors off/on (AOF_PLATFORM_ADMIN)
  AOF_ENV_NAME           dev | uat | prod … — named on exported versions
  AOF_PROMOTION_KEY      signs exported versions; imports must carry a valid signature
  AOF_NOTIFY_WEBHOOK_URL every notification is also POSTed here (Teams / Power Automate)
  AOF_CONSOLE_URL        the console's address, for links in notifications
  AOF_DOCUMENTS_DIR      documents the documents service reads (per scope)
  AOF_REPORTS_STORE      db (default) | fs — where PDF reports are kept
  AOF_REPORTS_DIR        the folder, when AOF_REPORTS_STORE=fs
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
# The folder that holds the agent_one_finance package: apps/backend here, the repo root in
# aos-backend. Defaults are looked for in both layouts.
PACKAGE_HOME = Path(__file__).resolve().parents[1]


def _default(*candidates: Path) -> Path:
    return next((c for c in candidates if c.exists()), candidates[0])


def _database_url_from_parts() -> str | None:
    """AOF_DATABASE_HOST, _PORT, _NAME, _USER, _PASSWORD as one URL, when only the parts are given
    (a container gets each key of a database secret as its own variable)."""
    from urllib.parse import quote

    host = os.getenv("AOF_DATABASE_HOST")
    if not host:
        return None
    user = quote(os.getenv("AOF_DATABASE_USER") or "", safe="")
    password = quote(os.getenv("AOF_DATABASE_PASSWORD") or "", safe="")
    login = f"{user}:{password}@" if password else (f"{user}@" if user else "")
    return f"postgresql+asyncpg://{login}{host}:{os.getenv('AOF_DATABASE_PORT') or '5432'}/{os.getenv('AOF_DATABASE_NAME') or 'postgres'}"


@dataclass(frozen=True)
class AofSettings:
    database_url: str
    config_dir: Path
    llm_adapter: str
    tracing_setup: str | None
    phoenix_endpoint: str | None
    phoenix_project: str
    entitlement_url: str | None
    entitlement_ttl_seconds: int
    console_origin: str
    identity_header: str
    trusted_proxy_secret: str | None
    proxy_secret_header: str
    entitlement_webhook_secret: str | None
    run_mode: str
    console_url: str
    scheduler: bool
    event_secret: str | None
    admin_role: str
    env_name: str
    path_prefix: str
    promotion_key: str | None
    notify_webhook_url: str | None
    documents_dir: Path
    reports_dir: Path
    reports_store: str


@lru_cache
def settings() -> AofSettings:
    env = os.getenv
    return AofSettings(
        # Same database as the rest of the app unless told otherwise.
        database_url=env("AOF_DATABASE_URL")
        or _database_url_from_parts()
        or env("FOBO_DATABASE_URL")
        or "postgresql+asyncpg://fobo:fobo@localhost:5433/fobo",
        config_dir=Path(env("AOF_CONFIG_DIR") or _default(REPO_ROOT / "config" / "agent-one-finance",
                                                           PACKAGE_HOME / "config" / "agent-one-finance")),
        llm_adapter=env("AOF_LLM_ADAPTER") or "stub",
        tracing_setup=env("AOF_TRACING_SETUP") or None,
        phoenix_endpoint=env("PHOENIX_COLLECTOR_ENDPOINT") or None,
        phoenix_project=env("PHOENIX_PROJECT_NAME") or "aof",
        entitlement_url=env("AOF_ENTITLEMENT_URL") or None,
        entitlement_ttl_seconds=int(env("AOF_ENTITLEMENT_TTL_SECONDS") or 60),
        console_origin=env("AOF_CONSOLE_ORIGIN") or "http://localhost:3100",
        # Who is calling. In the office, the SSO proxy's header (e.g. X-Remote-User).
        identity_header=env("AOF_IDENTITY_HEADER") or "X-AOF-User",
        # Set in the office: the SSO proxy adds this secret to every request it
        # forwards, so the identity header is trusted only from the proxy.
        trusted_proxy_secret=env("AOF_TRUSTED_PROXY_SECRET") or None,
        proxy_secret_header=env("AOF_PROXY_SECRET_HEADER") or "X-AOF-Proxy-Secret",
        # The entitlements service calls /api/entitlements/invalidate with it.
        entitlement_webhook_secret=env("AOF_ENTITLEMENT_WEBHOOK_SECRET") or None,
        # background: case runs leave the request path; inline: they finish first.
        run_mode=env("AOF_RUN_MODE") or "background",
        # The schedule loop runs in the API (on by default when runs are in the background).
        scheduler=(env("AOF_SCHEDULER") or ("on" if (env("AOF_RUN_MODE") or "background") == "background" else "off")) == "on",
        # Other systems open cases with POST /api/events, sending this secret.
        event_secret=env("AOF_EVENT_SECRET") or None,
        # Platform support: may switch connectors (and anything else) off and on.
        admin_role=env("AOF_ADMIN_ROLE") or "AOF_PLATFORM_ADMIN",
        # Promotion across environments: this deployment's name, and the key that
        # signs exported versions (shared by the environments that trust each other).
        env_name=env("AOF_ENV_NAME") or "dev",
        path_prefix=(env("AOF_PATH_PREFIX") or "").rstrip("/"),
        promotion_key=env("AOF_PROMOTION_KEY") or None,
        # Links in notifications point here.
        console_url=(env("AOF_CONSOLE_URL") or "http://localhost:5180").rstrip("/"),
        # Each notification is also POSTed here as JSON ({"text": …, "title": …, "link": …}):
        # a Teams incoming webhook, or a Power Automate flow that emails or posts it.
        notify_webhook_url=env("AOF_NOTIFY_WEBHOOK_URL") or None,
        # The documents service: what it reads, and where its reports go.
        documents_dir=Path(env("AOF_DOCUMENTS_DIR") or _default(PACKAGE_HOME / "seed_data" / "aof_documents")),
        reports_dir=Path(env("AOF_REPORTS_DIR") or REPO_ROOT / "var" / "agent-one-finance" / "reports"),
        # db: reports live in the shared database (every API instance serves them);
        # fs: in AOF_REPORTS_DIR (one server, or a shared mount)
        reports_store=env("AOF_REPORTS_STORE") or "db",
    )
