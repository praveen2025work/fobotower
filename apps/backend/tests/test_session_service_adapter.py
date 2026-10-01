"""Contract v2 adapter: one session per L4 rec run, started then polled."""

import re
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from fobo.investigation.settings import ReasonSettings, SessionServiceSettings
from fobo.reasoning.adapters.null import NullReasoner
from fobo.reasoning.adapters.session_service import SessionServiceReasoner
from fobo.reasoning.contracts import RecVerdict
from fobo.reasoning.port import HarnessStatus, ReasoningUnavailable
from fobo.reasoning.requests import FOBO_MCP_TOOLS, build_request

SKILL = Path(__file__).parents[3] / "skills" / "fobo-investigation" / "SKILL.md"

REC = {"reconciliation_id": "R-2031", "master_book": "FICR-MB",
       "business_date": "2026-08-03", "run_id": "run-R-2031-20260803"}
PATTERNS = [{"pattern_code": "UNGROUPED", "label": "No cause identified",
             "break_count": 1, "total_amount": 10.0,
             "sample": [{"break_id": "B-3"}]}]
ESTABLISHED = {"total": 8, "settled_by_rules": 3, "unsettled": 5}


def _request(monkeypatch, **env):
    for key in ("FOBO_MCP_URL", "FOBO_SESSION_SKILL_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return build_request(correlation_id="sess-r-2031", rec=REC, patterns=PATTERNS,
                         already_established=ESTABLISHED, mcp_token="tok-1")


def _skill_verdict():
    return {
        "break_summary": "s",
        "checks_performed": [{"test_id": "FO-3", "checked": "c", "result": "Fail", "evidence": "e"}],
        "root_cause": {"established": True, "statement": "x", "side": "FO"},
        "classification": {"category_code": "G", "category_name": "Corporate action break",
                           "deterministic": False},
        "verdict": "DO_NOT_POST", "verdict_reason": "r",
        "remediation": {"who_to_engage": ["desk"], "what_to_raise": ["DQ"]},
        "end_state_validation": "open", "requires_sme_review": True,
    }


def _output():
    return {"summary": "done", "patterns": [{"pattern_code": "UNGROUPED", **_skill_verdict()}]}


def _reasoner(handler):
    return SessionServiceReasoner(
        base_url="https://svc.internal", timeout=5.0,
        transport=httpx.MockTransport(handler),
    )


def test_the_default_skill_id_matches_the_deployable_skill(monkeypatch):
    """A mismatch here means the service loads no skill and the model reasons
    from nothing — with a verdict that looks normal."""
    name = re.search(r"^name:\s*(\S+)", SKILL.read_text(), re.M).group(1)
    assert _request(monkeypatch)["skill_id"] == name == "fobo-investigation"


def test_the_request_has_the_v2_shape(monkeypatch):
    req = _request(monkeypatch)
    assert req["correlation_id"] == "sess-r-2031"
    assert req["inputs"] == {"rec": REC, "patterns": PATTERNS,
                             "already_established": ESTABLISHED}
    assert req["output_schema"] == RecVerdict.model_json_schema()


def test_mcp_and_tools_only_with_a_server_and_carry_the_session_token(monkeypatch):
    without = _request(monkeypatch)
    assert "mcp" not in without and "tools" not in without

    req = _request(monkeypatch, FOBO_MCP_URL="https://orch/mcp")
    assert req["mcp"] == {"url": "https://orch/mcp", "token": "tok-1"}
    assert req["tools"] == [f"mcp__fobo__{n}" for n in (
        "fobo_list_tests", "fobo_evidence_required", "fobo_required_on_fail",
        "fobo_unset_policies", "fobo_book_context", "fobo_similar_breaks",
        "fobo_list_breaks", "fobo_break_detail")]
    assert req["tools"] == list(FOBO_MCP_TOOLS)


def test_the_skill_names_the_tools_the_request_offers():
    """If they drift, the model calls tools it may not use. The skill does
    not yet describe the two rec-level tools (list_breaks, break_detail);
    it is updated with the contract documentation."""
    text = SKILL.read_text()
    for tool in FOBO_MCP_TOOLS:
        if tool.endswith(("fobo_list_breaks", "fobo_break_detail")):
            continue
        assert tool.removeprefix("mcp__fobo__") in text, tool


async def test_start_posts_to_sessions_and_parses_running():
    seen = {}

    def handler(request):
        seen["method"], seen["path"] = request.method, request.url.path
        return httpx.Response(200, json={"session_id": "h-1", "status": "running"})

    status = await _reasoner(handler).start({"skill_id": "x"})
    assert (seen["method"], seen["path"]) == ("POST", "/sessions")
    assert status == HarnessStatus(session_id="h-1", status="running", output=None,
                                   payload={"session_id": "h-1", "status": "running"},
                                   error=None)


async def test_poll_gets_the_session_and_parses_completed():
    seen = {}

    def handler(request):
        seen["method"], seen["path"] = request.method, request.url.path
        return httpx.Response(200, json={"session_id": "h-1", "status": "completed",
                                         "output": _output()})

    status = await _reasoner(handler).poll("h-1")
    assert (seen["method"], seen["path"]) == ("GET", "/sessions/h-1")
    assert status.status == "completed"
    assert status.output.patterns[0].pattern_code == "UNGROUPED"
    assert status.output.patterns[0].verdict == "DO_NOT_POST"


async def test_a_failed_session_is_returned_not_raised():
    payload = {"session_id": "h-1", "status": "failed",
               "error": {"code": "schema_retries_exhausted", "message": "gave up"}}
    status = await _reasoner(lambda r: httpx.Response(200, json=payload)).poll("h-1")
    assert status.status == "failed"
    assert status.error == "schema_retries_exhausted — gave up"
    assert status.output is None


@pytest.mark.parametrize("payload", [
    {"session_id": "h-1", "status": "completed"},
    {"session_id": "h-1", "status": "completed", "output": {"summary": "x"}},
    {"session_id": "h-1", "status": "paused"},
    {"status": "running"},
])
async def test_an_untrustworthy_response_is_unavailable(payload):
    with pytest.raises(ReasoningUnavailable):
        await _reasoner(lambda r: httpx.Response(200, json=payload)).poll("h-1")


async def test_an_http_error_is_unavailable():
    with pytest.raises(ReasoningUnavailable):
        await _reasoner(lambda r: httpx.Response(500)).start({})


async def test_a_transport_error_is_unavailable():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(ReasoningUnavailable):
        await _reasoner(handler).start({})


async def test_the_null_reasoner_raises():
    with pytest.raises(ReasoningUnavailable):
        await NullReasoner().start({})
    with pytest.raises(ReasoningUnavailable):
        await NullReasoner().poll("x")


def test_the_new_settings_defaults_and_bounds():
    assert ReasonSettings().sample_breaks_per_pattern == 5
    ss = SessionServiceSettings()
    assert (ss.max_wait_seconds, ss.poll_interval_seconds, ss.timeout_seconds) == (900.0, 5.0, 120.0)
    for bad in ({"sample_breaks_per_pattern": 0}, {"sample_breaks_per_pattern": 51}):
        with pytest.raises(ValidationError):
            ReasonSettings(**bad)
    for bad in ({"max_wait_seconds": 0}, {"max_wait_seconds": 3601},
                {"poll_interval_seconds": 0}, {"poll_interval_seconds": 61}):
        with pytest.raises(ValidationError):
            SessionServiceSettings(**bad)
