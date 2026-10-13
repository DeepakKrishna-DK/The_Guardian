"""
Guardian Telemetry — guardian/telemetry/tracer.py
===================================================
OpenTelemetry tracing, OFF by default (no-op unless configured).

Usage:
    from guardian.telemetry.tracer import configure, get_tracer, current_trace_id

    # In tests: inject an in-memory provider
    configure(provider=my_provider)

    # In production: read GUARDIAN_OTEL_EXPORTER env var
    configure()

Spans:
    guardian.process           - root span for each orchestrator turn
    guardian.guardrail.input   - input guardrail scan
    guardian.guardrail.output  - output guardrail scan
    guardian.model.call        - model inference (attrs: provider, model, locality)
    guardian.policy.evaluate   - policy decision (attrs: tool, effect, rule_id)
    guardian.tool.run          - tool execution (attrs: tool, tier, decision)

Attribute rule: metadata ONLY. Never include prompt, response, tool output,
or secrets. Violating this rule creates a data exfiltration channel.

Env:
    GUARDIAN_OTEL_EXPORTER = none (default, no-op) | console

Apache-2.0. opentelemetry-api and opentelemetry-sdk are Apache-2.0.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import NonRecordingSpan, Tracer

_TRACER_NAME = "guardian"
_provider: TracerProvider | None = None
_tracer: Tracer | None = None


def configure(
    provider: TracerProvider | None = None,
    exporter_name: str | None = None,
) -> None:
    """
    Configure the tracing subsystem.

    Args:
        provider: Inject a TracerProvider (for testing with InMemorySpanExporter).
                  If None, reads GUARDIAN_OTEL_EXPORTER env var.
        exporter_name: Override GUARDIAN_OTEL_EXPORTER ("none" | "console").
    """
    global _provider, _tracer

    if provider is not None:
        _provider = provider
        _tracer = _provider.get_tracer(_TRACER_NAME)
        return

    exp_name = exporter_name or os.environ.get("GUARDIAN_OTEL_EXPORTER", "none")

    if exp_name == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        p = TracerProvider()
        p.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        _provider = p
    else:
        # Default: no-op (no exporter registered)
        _provider = TracerProvider()

    _tracer = _provider.get_tracer(_TRACER_NAME)


def get_tracer() -> Tracer:
    """Return the configured tracer (no-op if not configured)."""
    global _tracer
    if _tracer is None:
        configure()
    return _tracer  # type: ignore[return-value]


def current_trace_id() -> str | None:
    """Return the current trace ID as a hex string, or None if no active span."""
    span = trace.get_current_span()
    if isinstance(span, NonRecordingSpan):
        return None
    ctx = span.get_span_context()
    if ctx and ctx.trace_id:
        return format(ctx.trace_id, "032x")
    return None


def reset() -> None:
    """Reset tracer state (for tests only)."""
    global _provider, _tracer
    _provider = None
    _tracer = None


@contextmanager
def span(name: str, **attrs: str | int | float | bool) -> Generator[trace.Span, None, None]:
    """
    Context manager for a traced span.

    Attributes must be metadata only — never pass prompt/response/tool content.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as s:
        for k, v in attrs.items():
            s.set_attribute(k, v)
        yield s
