"""Delegates reasoning to an existing session service (contract v2).

The service owns the model call, the skill upload, and any MCP tool wiring.
This adapter's whole job is two HTTP calls: start a session for one L4 rec
run, and poll it until it completes. The request is built by
fobo.reasoning.requests.build_request; the waiting loop lives in the Reason
step, so each method here is a single request.

Configuration:
    FOBO_REASONER=session_service
    FOBO_SESSION_SERVICE_URL   base URL of the service
    FOBO_SESSION_SERVICE_TOKEN bearer token, if it requires one
    FOBO_SESSION_SKILL_ID      the skill the service should apply
    FOBO_MCP_URL               this orchestrator's MCP server; when set the
                               request offers it (with a per-session token)

The shape is specified in docs/integration/session-service-contract.md.
"""

import os

import httpx
from pydantic import ValidationError

from fobo.reasoning.contracts import RecVerdict
from fobo.reasoning.port import HarnessStatus, ReasoningUnavailable

_STATUSES = ("running", "completed", "failed")


def _parse_status(payload: dict) -> HarnessStatus:
    status = payload.get("status")
    if status not in _STATUSES:
        raise ReasoningUnavailable(f"session service returned unknown status {status!r}")
    session_id = payload.get("session_id")
    if not session_id:
        raise ReasoningUnavailable("session service response has no session_id")
    if status == "failed":
        err = payload.get("error") or {}
        return HarnessStatus(
            session_id=session_id, status="failed", payload=payload,
            error=f"{err.get('code', '?')} — {err.get('message', '')}",
        )
    if status == "running":
        return HarnessStatus(session_id=session_id, status="running", payload=payload)
    if payload.get("output") is None:
        raise ReasoningUnavailable("session completed without an output")
    try:
        output = RecVerdict.model_validate(payload["output"])
    except ValidationError as exc:
        raise ReasoningUnavailable(
            f"session service returned an unparseable verdict: {exc}"
        ) from exc
    return HarnessStatus(
        session_id=session_id, status="completed", output=output, payload=payload
    )


class SessionServiceReasoner:
    name = "session_service"

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._base_url = (base_url or os.getenv("FOBO_SESSION_SERVICE_URL", "")).rstrip(
            "/"
        )
        self._token = token or os.getenv("FOBO_SESSION_SERVICE_TOKEN")
        if timeout is None:
            from fobo.investigation.settings import settings

            timeout = settings().session_service.timeout_seconds
        self._timeout = timeout
        # Injected by tests; None means a real network connection.
        self._transport = transport
        if not self._base_url:
            raise ReasoningUnavailable("FOBO_SESSION_SERVICE_URL is not set")

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _call(self, method: str, path: str, **kwargs) -> HarnessStatus:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.request(
                    method, f"{self._base_url}{path}", headers=self._headers(), **kwargs
                )
                response.raise_for_status()
                return _parse_status(response.json())
        except ReasoningUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced, never swallowed
            raise ReasoningUnavailable(f"session service call failed: {exc}") from exc

    async def start(self, request: dict) -> HarnessStatus:
        return await self._call("POST", "/sessions", json=request)

    async def poll(self, session_id: str) -> HarnessStatus:
        return await self._call("GET", f"/sessions/{session_id}")
