"""Delegates reasoning to an existing session service.

The service owns the model call, the skill upload, and any MCP tool wiring.
This adapter's whole job is to hand over one break's evidence and parse the
§12 verdict back.

Configuration:
    FOBO_REASONER=session_service
    FOBO_SESSION_SERVICE_URL   base URL of the service
    FOBO_SESSION_SERVICE_TOKEN bearer token, if it requires one
    FOBO_SESSION_SKILL_ID      the skill the service should apply

    FOBO_MCP_URL               this orchestrator's MCP server, handed to the
                               session so the model can query the graph
    FOBO_MCP_TOKEN             bearer token the session uses against it

The service runs each request through the Claude Agent SDK. The shape is
specified in docs/integration/session-service-contract.md, and isolated to
_build_request and _parse_response here.
"""

import os

import httpx
from pydantic import ValidationError

from app.reasoning.contracts import SkillVerdict
from app.reasoning.port import ReasoningUnavailable

DEFAULT_TIMEOUT_SECONDS = 120.0

# The orchestrator's graph and engines, as the model sees them.
FOBO_MCP_TOOLS = (
    "mcp__fobo__fobo_list_tests",
    "mcp__fobo__fobo_evidence_required",
    "mcp__fobo__fobo_required_on_fail",
    "mcp__fobo__fobo_similar_breaks",
    "mcp__fobo__fobo_book_context",
    "mcp__fobo__fobo_unset_policies",
)


class SessionServiceReasoner:
    name = "session_service"

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        skill_id: str | None = None,
        timeout: float | None = None,
    ):
        self._base_url = (base_url or os.getenv("FOBO_SESSION_SERVICE_URL", "")).rstrip(
            "/"
        )
        self._token = token or os.getenv("FOBO_SESSION_SERVICE_TOKEN")
        # Must match the `name` in skills/fobo-investigation/SKILL.md.
        self._skill_id = skill_id or os.getenv(
            "FOBO_SESSION_SKILL_ID", "fobo-investigation"
        )
        self._mcp_url = os.getenv("FOBO_MCP_URL")
        self._mcp_token = os.getenv("FOBO_MCP_TOKEN")
        if timeout is None:
            from app.workflow.config import settings

            timeout = settings().session_service.timeout_seconds
        self._timeout = timeout
        if not self._base_url:
            raise ReasoningUnavailable("FOBO_SESSION_SERVICE_URL is not set")

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _build_request(self, evidence: dict) -> dict:
        """One break, one session. The skill is named, not inlined: the
        service holds it on disk, and re-sending it per break would pay for
        the same tokens on every call."""
        request = {
            "skill_id": self._skill_id,
            "correlation_id": evidence.get("correlation_id") or evidence.get("break_id"),
            "inputs": {
                "break_record": {
                    k: v for k, v in evidence.items() if k != "already_established"
                },
                "already_established": evidence.get("already_established", {}),
            },
            "output_schema": SkillVerdict.model_json_schema(),
        }
        # Only offer the graph as tools when there is one to offer. Naming an
        # unreachable MCP server would fail the session for no benefit.
        if self._mcp_url:
            request["mcp"] = {"url": self._mcp_url, "token": self._mcp_token}
            request["tools"] = list(FOBO_MCP_TOOLS)
        return request

    def _parse_response(self, payload: dict) -> SkillVerdict:
        status = payload.get("status")
        if status in ("failed", "refused"):
            err = payload.get("error") or {}
            raise ReasoningUnavailable(
                f"session {status}: {err.get('code', '?')} — {err.get('message', '')}"
            )
        # Accept either a bare verdict or one nested under a result envelope.
        body = payload.get("output") or payload.get("result") or payload
        try:
            return SkillVerdict.model_validate(body)
        except ValidationError as exc:
            raise ReasoningUnavailable(
                f"session service returned an unparseable verdict: {exc}"
            ) from exc

    async def investigate(self, evidence: dict) -> SkillVerdict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/sessions",
                    json=self._build_request(evidence),
                    headers=self._headers(),
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except ReasoningUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced, never swallowed
            raise ReasoningUnavailable(f"session service call failed: {exc}") from exc
