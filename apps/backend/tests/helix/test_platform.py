"""Entitlement, tracing, and the boundary between the platform and FOBO."""

import ast
from pathlib import Path

import httpx
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from helix.entitlement import EntitlementError, HttpEntitlement
from tests.helix.conftest import VARIANCE

HELIX = Path(__file__).resolve().parents[2] / "helix"


def test_the_platform_never_imports_fobo():
    offenders = []
    for path in HELIX.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            offenders += [f"{path.name}: {n}" for n in names if n.split(".")[0] in ("fobo", "seed_data")]
    assert offenders == []


def _service(handler):
    return HttpEntitlement("https://ent.example/api", transport=httpx.MockTransport(handler))


async def test_central_entitlement_roles_and_data_scopes():
    def handler(request):
        assert request.url.path == "/api/users/u1/entitlements"
        assert request.url.params["app"] == "helix"
        return httpx.Response(200, json={"roles": ["FIN_PREPARER"],
                                         "data_scopes": {"entity": ["UK01"]}})
    caller = await _service(handler).get("u1")
    assert caller.roles == {"FIN_PREPARER"}
    assert caller.may_see("entity", "UK01") and not caller.may_see("entity", "US01")
    assert not caller.may_see("book", "B1")  # no scope for a dimension means nothing


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500),
    lambda r: httpx.Response(404),
    lambda r: httpx.Response(200, text="not json"),
])
async def test_entitlement_fails_closed(handler):
    with pytest.raises(EntitlementError):
        await _service(handler).get("u1")


async def test_entitlement_service_down_fails_closed():
    def handler(request):
        raise httpx.ConnectError("refused")
    with pytest.raises(EntitlementError, match="unavailable"):
        await _service(handler).get("u1")


@pytest.fixture(scope="module")
def spans():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


async def test_one_case_is_one_trace_with_helix_attributes(api, spans):
    spans.clear()
    case = (await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("alice"),
                           json={"case_key": {"entity": "UK01", "period": "2026-09"}})).json()
    finished = spans.get_finished_spans()
    names = {s.name for s in finished}
    assert {"case.run", "step.load", "step.validate", "mcp.call", "reason.group"} <= names
    root = next(s for s in finished if s.name == "case.run")
    assert root.attributes["helix.case_id"] == case["case_id"]
    assert root.attributes["helix.capability_id"] == VARIANCE
    # the case run is its own trace — a root span, not a child of the HTTP request —
    # and every step, tool call and reasoning span of the run is inside it
    assert root.parent is None
    run_spans = [s for s in finished if s.name.startswith(("step.", "mcp.call", "reason."))]
    assert run_spans and {s.context.trace_id for s in run_spans} == {root.context.trace_id}
    assert root.attributes["session.id"] == case["case_id"]
    assert root.attributes["openinference.span.kind"] == "CHAIN"
    assert case["trace_id"] == format(root.context.trace_id, "032x")
    call = next(s for s in finished if s.name == "mcp.call")
    assert call.attributes["helix.connector_id"] == "gl"
    assert call.attributes["helix.allowed"] is True
