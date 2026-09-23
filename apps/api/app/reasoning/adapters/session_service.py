"""Delegates reasoning to an existing session service.

The service owns the model call, the skill upload, and any MCP tool wiring.
This adapter's whole job is to hand over one break's evidence and parse the
§12 verdict back.

Configuration:
    FOBO_REASONER=session_service
    FOBO_SESSION_SERVICE_URL   base URL of the service
    FOBO_SESSION_SERVICE_TOKEN bearer token, if it requires one
    FOBO_SESSION_SKILL_ID      the skill the service should apply

The request shape below is a placeholder pending the service's actual
contract — it is isolated to _build_request and _parse_response so adapting
it is a two-function change, not a rewrite.
"""

import os

import httpx
from pydantic import ValidationError

from app.reasoning.contracts import SkillVerdict
from app.reasoning.port import ReasoningUnavailable

DEFAULT_TIMEOUT_SECONDS = 120.0


class SessionServiceReasoner:
    name = "session_service"

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        skill_id: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._base_url = (base_url or os.getenv("FOBO_SESSION_SERVICE_URL", "")).rstrip(
            "/"
        )
        self._token = token or os.getenv("FOBO_SESSION_SERVICE_TOKEN")
        self._skill_id = skill_id or os.getenv(
            "FOBO_SESSION_SKILL_ID", "fobo-cats-vs-motif"
        )
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
        service already holds it, and re-uploading it per break would pay
        for the same tokens on every call."""
        return {
            "skill_id": self._skill_id,
            "inputs": {"break_record": evidence},
            "output_schema": SkillVerdict.model_json_schema(),
        }

    def _parse_response(self, payload: dict) -> SkillVerdict:
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
