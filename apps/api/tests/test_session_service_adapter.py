import json
import re
from pathlib import Path

import pytest

from app.reasoning.adapters.session_service import FOBO_MCP_TOOLS, SessionServiceReasoner
from app.reasoning.contracts import SkillVerdict
from app.reasoning.port import ReasoningUnavailable

CONTRACT = Path(__file__).parents[3] / "docs" / "integration" / "session-service-contract.md"
SKILL = Path(__file__).parents[3] / "skills" / "fobo-investigation" / "SKILL.md"


def _reasoner(monkeypatch, **env):
    for key in ("FOBO_MCP_URL", "FOBO_MCP_TOKEN", "FOBO_SESSION_SKILL_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return SessionServiceReasoner(base_url="https://svc.internal")


def _documented(i):
    return json.loads(re.findall(r"```json\n(.*?)```", CONTRACT.read_text(), re.S)[i])


def test_the_default_skill_id_matches_the_deployable_skill(monkeypatch):
    """A mismatch here means the service loads no skill and the model reasons
    from nothing — with a verdict that looks normal."""
    name = re.search(r"^name:\s*(\S+)", SKILL.read_text(), re.M).group(1)
    req = _reasoner(monkeypatch)._build_request({"break_id": "B-7"})
    assert req["skill_id"] == name == "fobo-investigation"


def test_the_request_carries_the_break_and_what_is_already_established(monkeypatch):
    req = _reasoner(monkeypatch)._build_request({
        "break_id": "B-7", "fo_value": 0.0,
        "already_established": {"deterministic_findings": ["FO-1 pass"]},
    })
    assert req["inputs"]["break_record"]["break_id"] == "B-7"
    assert "already_established" not in req["inputs"]["break_record"]
    assert req["inputs"]["already_established"]["deterministic_findings"] == ["FO-1 pass"]
    assert req["correlation_id"] == "B-7"


def test_the_output_schema_is_the_skill_verdict(monkeypatch):
    req = _reasoner(monkeypatch)._build_request({"break_id": "B-7"})
    assert req["output_schema"] == SkillVerdict.model_json_schema()


def test_mcp_tools_are_offered_only_when_a_server_is_configured(monkeypatch):
    """Naming an unreachable MCP server would fail the session for nothing."""
    without = _reasoner(monkeypatch)._build_request({"break_id": "B-7"})
    assert "mcp" not in without and "tools" not in without

    with_mcp = _reasoner(monkeypatch, FOBO_MCP_URL="https://orch/mcp",
                         FOBO_MCP_TOKEN="t")._build_request({"break_id": "B-7"})
    assert with_mcp["mcp"] == {"url": "https://orch/mcp", "token": "t"}
    assert with_mcp["tools"] == list(FOBO_MCP_TOOLS)


def test_every_offered_tool_follows_the_agent_sdk_mcp_naming(monkeypatch):
    for tool in FOBO_MCP_TOOLS:
        assert tool.startswith("mcp__fobo__fobo_")


def test_the_skill_names_the_same_tools_the_adapter_offers():
    """The skill tells the model which tools to call; the adapter decides
    which are allowed. If they drift, the model calls tools it may not use."""
    text = SKILL.read_text()
    for tool in FOBO_MCP_TOOLS:
        assert tool.removeprefix("mcp__fobo__") in text, tool


def test_the_documented_request_shape_matches_what_the_adapter_builds(monkeypatch):
    documented = _documented(0)
    built = _reasoner(monkeypatch, FOBO_MCP_URL="u", FOBO_MCP_TOKEN="t")._build_request(
        {"break_id": "B-7"}
    )
    assert set(documented) <= set(built) | {"output_schema"}


def test_the_documented_response_parses(monkeypatch):
    verdict = _reasoner(monkeypatch)._parse_response(_documented(1))
    assert verdict.verdict == "DO_NOT_POST"
    assert verdict.root_cause.side == "FO"


@pytest.mark.parametrize("payload", [
    {"status": "failed", "error": {"code": "schema_retries_exhausted", "message": "x"}},
    {"status": "failed", "error": {"code": "skill_not_loaded", "message": "x"}},
    {"status": "refused"},
])
def test_a_failed_session_is_unavailable_not_a_verdict(monkeypatch, payload):
    """'Could not reason' must never be read as 'reasoned, and escalate'."""
    with pytest.raises(ReasoningUnavailable):
        _reasoner(monkeypatch)._parse_response(payload)
