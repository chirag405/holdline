"""Turn on Strands' built-in OpenTelemetry tracing.

Every agent turn, tool call, and model request in Strands is already
instrumented; this just wires up exporters:

- OTLP if OTEL_EXPORTER_OTLP_ENDPOINT is set (point it at a collector / Jaeger /
  Langfuse / AWS X-Ray via the ADOT collector).
- console spans if TRACING_CONSOLE=true (handy locally; noisy).

Called once at process start (bridge import + run_bridge.py). Safe to call twice.
"""

from __future__ import annotations

import os

import structlog

from holdline.config import get_settings

log = structlog.get_logger("telemetry")

_done = False


def init_telemetry() -> None:
    global _done
    if _done:
        return
    _done = True

    s = get_settings()
    if not s.tracing_enabled:
        return

    os.environ.setdefault("OTEL_SERVICE_NAME", s.otel_service_name)
    try:
        from strands.telemetry import StrandsTelemetry

        t = StrandsTelemetry()
        has_otlp = bool(
            os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        )
        if has_otlp:
            t.setup_otlp_exporter()
        if s.tracing_console:
            t.setup_console_exporter()
        t.setup_meter(
            enable_console_exporter=s.tracing_console,
            enable_otlp_exporter=has_otlp,
        )
        log.info("telemetry.on", service=s.otel_service_name, otlp=has_otlp, console=s.tracing_console)
    except Exception as exc:  # noqa: BLE001 - tracing must never block the app
        log.warning("telemetry.init_failed", error=str(exc))


__all__ = ["init_telemetry"]
