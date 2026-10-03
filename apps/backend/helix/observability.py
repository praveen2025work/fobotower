"""Tracing, through the OpenTelemetry API only.

Helix never depends on a tracing backend. With no provider configured every
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

            register(project_name="helix", endpoint=s.phoenix_endpoint, auto_instrument=True)
            return f"phoenix: {s.phoenix_endpoint}"
    except Exception:  # never let tracing stop the app
        log.exception("tracing setup failed; continuing without traces")
        return "failed"
    return "none"


def _clean(value: Any):
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


@contextmanager
def span(name: str, **attributes: Any):
    """A span with `helix.*` attributes; None values are skipped."""
    with tracer.start_as_current_span(name) as s:
        for key, value in attributes.items():
            if value is not None:
                s.set_attribute(f"helix.{key}", _clean(value))
        yield s


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None
