# Observability

Strands instruments every agent turn, tool call, and model request with
OpenTelemetry out of the box. Holdline turns on the exporters in
`src/holdline/telemetry.py`, called once at process start.

## Local — console spans

```bash
TRACING_CONSOLE=true python scripts/run_bridge.py
```

Spans print to the bridge log: one trace per call, with child spans for the
Planner, each Caller model turn, `press_keys` / `escalate_to_user` tool calls,
the Supervisor reviews, and the Scribe.

## To a collector (for the README screenshot)

Any OTLP-compatible backend works — Jaeger, Grafana Tempo, Langfuse, or the AWS
Distro for OpenTelemetry collector forwarding to X-Ray.

```bash
# Jaeger all-in-one
docker run --rm -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one:latest

OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python scripts/run_bridge.py
# run a call, then open http://localhost:16686  ->  service "holdline"
```

## What to look at

| Span / metric | Tells you |
|---|---|
| `Cycle` duration per Caller turn | voice-loop latency |
| `Tool - press_keys` / `Tool - escalate_to_user` | IVR navigation + how often a human was pulled in |
| `STRANDS_MODEL_TIME_TO_FIRST_TOKEN` | Nova Sonic responsiveness |
| trace span count per call | how much back-and-forth a cancellation took |
| `STRANDS_TOOL_ERROR_COUNT` | DTMF rejections, failed sends |

## Config

| env | default | |
|---|---|---|
| `TRACING_ENABLED` | `true` | master switch |
| `TRACING_CONSOLE` | `false` | print spans to stdout |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | – | set to enable OTLP export |
| `OTEL_SERVICE_NAME` | `holdline` | service name in the backend |
