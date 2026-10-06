"""Tracing, through the OpenTelemetry API only.

Agent One Finance never depends on a tracing backend. With no provider configured every
span is a no-op. To send traces to Phoenix (or anything OTLP), configure one
of these at startup — `setup_tracing()` is called once by the web app:

  HELIX_TRACING_SETUP="your_pkg.tracing:setup"   any callable you supply
  PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:6006  and `pip install arize-phoenix-otel`

A tracing failure never fails a run: spans are best effort; audit rows are
the record (helix/models.py).
"""

import logging
from contextlib import contextmanager
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace

from helix import plugins
from helix.config import settings

log = logging.getLogger(__name__)
tracer = trace.get_tracer("helix")
_configured = False


def setup_tracing() -> str:
    """Install the configured tracing backend once. Returns what was set up."""
    global _configured
    if _configured:
        return "already configured"
    _configured = True
    s = settings()
    try:
        if s.tracing_setup:
            plugins.load(s.tracing_setup)()
            return f"custom: {s.tracing_setup}"
        if s.phoenix_endpoint:
            from phoenix.otel import register  # optional dependency

            from helix.governance import configure_trace_hiding
            configure_trace_hiding()  # before instrumentors read their config

            # auto_instrument picks up every installed OpenInference instrumentor —
            # with the [phoenix] extra: the Claude Agent SDK and LangChain/LangGraph.
            register(project_name=s.phoenix_project, endpoint=_otlp_endpoint(s.phoenix_endpoint),
                     batch=True, auto_instrument=True, verbose=False)
            return f"phoenix: {s.phoenix_endpoint} (project {s.phoenix_project})"
    except Exception:  # never let tracing stop the app
        log.exception("tracing setup failed; continuing without traces")
        return "failed"
    return "none"


def _otlp_endpoint(base: str) -> str:
    """Phoenix accepts OTLP/HTTP at /v1/traces; accept the bare collector URL too."""
    base = base.rstrip("/")
    return base if base.endswith("/v1/traces") else f"{base}/v1/traces"


# OpenInference span kinds, so Phoenix renders Agent One Finance spans as chains, tools and agents.
CHAIN, TOOL, AGENT = "CHAIN", "TOOL", "AGENT"


def _clean(value: Any):
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


@contextmanager
def span(name: str, *, kind: str = CHAIN, input: Any = None, root: bool = False,
         **attributes: Any):
    """A span with `helix.*` attributes (None values skipped) plus the OpenInference
    conventions Phoenix reads: span kind, session.id (the case — Phoenix's Sessions
    view groups a case's runs), user.id, and input.value when given.

    root=True starts a new trace (linked to the caller's span, e.g. the HTTP
    request), so one case run is one trace in Phoenix, not a child of a request."""
    options = {}
    if root:
        parent = trace.get_current_span().get_span_context()
        options = {"context": otel_context.Context(),
                   "links": [trace.Link(parent)] if parent.is_valid else []}
    with tracer.start_as_current_span(name, **options) as s:
        s.set_attribute("openinference.span.kind", kind)
        if attributes.get("case_id"):
            s.set_attribute("session.id", attributes["case_id"])
        if attributes.get("user"):
            s.set_attribute("user.id", attributes["user"])
        if input is not None:
            s.set_attribute("input.value", _json(input))
            s.set_attribute("input.mime_type", "application/json")
        for key, value in attributes.items():
            if value is not None:
                s.set_attribute(f"helix.{key}", _clean(value))
        yield s


def set_output(s, value: Any) -> None:
    """Record a span's output for Phoenix (already masked by the caller)."""
    s.set_attribute("output.value", _json(value))
    s.set_attribute("output.mime_type", "application/json")


def _json(value: Any) -> str:
    import json

    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text[:20000]  # keep spans bounded; the full record is the audit row


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None
