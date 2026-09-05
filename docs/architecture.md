# Holdline — Architecture

> Diagram: [`architecture.png`](architecture.png) / [`architecture.mmd`](architecture.mmd),
> and the mermaid block in the top-level [`README.md`](../README.md).

## Components

### Agents (Strands)

| Agent | Type | Runs | Responsibility |
|---|---|---|---|
| **Planner** | text `Agent`, structured output | once, pre-call | Turn a plain-language request + optional fields into a **Call Brief**: `objective`, `identity_info`, `boundaries {may_agree_to, must_escalate}`, `success_criteria`, `ivr_hint`, `default_on_timeout`. Reads AgentCore Memory for a known provider's IVR path. |
| **Caller** | `BidiAgent` + Nova 2 Sonic | during the call | Live voice conversation. Tools: `send_dtmf`, `escalate_to_user`, `lookup_task_context`, `record_outcome`, `end_call`. |
| **Supervisor** | text `Agent` | every ~8 s during the call | Reads the running transcript against the Brief; returns `{continue \| escalate(question, options) \| abort(reason)}`. Safety net + the multi-agent story. |
| **Scribe** | text `Agent` | once, post-call | Transcript → `summary`, `confirmation_number`, `outcome_status`, `follow_up_draft`, `follow_up_date`. Writes the learned IVR path back to Memory. |

Orchestration: **Strands `Graph`** (`holdline/graph.py`) — three `MultiAgentBase`
nodes, `planner → call → debrief`:
- **planner** — ensure a Brief exists (passthrough when the dashboard pre-planned
  via `POST /tasks`).
- **call** — run the live `CallSession`: Caller (`BidiAgent` + Nova Sonic) and
  Supervisor (`Agent`) concurrently on a shared asyncio transcript bus.
- **debrief** — Scribe the transcript, persist the call, write learned IVR paths
  to provider memory, emit `call_ended`.

`USE_GRAPH=false` runs the same steps without the Graph wrapper.

### Telephony bridge (`src/holdline/telephony/`)

- `POST /calls` → Twilio REST `calls.create` with TwiML `<Connect><Stream url=wss://…/ts>`,
  plus a `status_callback` to `/call-status`.
- WS `/ts`: Twilio `media` frames (G.711 μ-law 8 kHz base64) ⇄ linear PCM16
  8 kHz — Nova Sonic runs at `input_rate=output_rate=8000` so the hot path needs
  no resampling (`audio.py` keeps a streamed resampler for the 16k/24k fallback).
  Barge-in (`BidiInterruptionEvent`) → Twilio `clear`.
- `send_dtmf`: real DTMF dual-tones synthesized as μ-law and injected as `media`
  frames — Media Streams has no send-DTMF message, and this keeps the stream
  alive. `press_keys` falls back to telling the Caller to speak the digits.
- `POST /call-status`: Twilio call-lifecycle webhook. `busy` / `no-answer` /
  `failed` / `canceled` with no media stream ever connected → a recorded failure
  instead of a task stuck in `calling`.

### Dashboard API + live stream

`GET /config`, `GET /tasks/{id}`, `GET /calls`, `GET /calls/{id}`, and
`GET /stream` — Server-Sent Events (`turn`, `status`, `decision_open`,
`decision_resolved`, `call_ended`) that the Next.js dashboard folds into the live
call view. Events come from `holdline/events.py` (in-process pub/sub + a replay
buffer).

### Escalation (the human-in-the-loop)

On `escalate`: Caller speaks a holding phrase and goes quiet → write a `decisions`
row → push to the dashboard Decision card (question + options + countdown) → wait
≤ 90 s for the user's answer → inject answer into Caller context → resume. Timeout →
`Brief.default_on_timeout`. The line stays open the whole time.

### State (DynamoDB, `src/holdline/state/`)

| Table | Key fields |
|---|---|
| `holdline-tasks` | `task_id`, request text, fields, `brief` (JSON), `status` |
| `holdline-calls` | `call_id`, `task_id`, `transcript`, `recording_url`, `outcome`, `confirmation_number`, timings |
| `holdline-decisions` | `decision_id`, `call_id`, `question`, `options`, `answer`, `resolved_at` |

### Provider memory (`src/holdline/memory.py`)

`get_provider_hint(name)` / `record_call_learnings(name, ivr_path, outcome, …)`.
Two backends behind `MEMORY_BACKEND`:

- `local` (default) — in-process dict, seeded with the practice line's menu path.
- `agentcore` — Amazon Bedrock **AgentCore Memory** (`MemoryClient`), one event
  per call under session id `provider:<slug>`; durable across runs.

The Planner reads a provider's known IVR path before a call; the Scribe writes
the observed path back after. The second call to a provider starts already
knowing its menu.

### Error handling

Every failure lands as a recorded outcome, never a hang: no-answer/busy →
`/call-status`; mid-call drop → Scribe on the partial transcript; Nova stream
error before any transcript → clean `error` row, no Scribe; Planner (Bedrock)
failure → degraded plain brief; DTMF rejected → speak-the-digits fallback;
transferred in circles → Supervisor `abort`.

### Observability

Strands' built-in OpenTelemetry, wired in `src/holdline/telemetry.py`. Console
spans with `TRACING_CONSOLE=true`; OTLP export when `OTEL_EXPORTER_OTLP_ENDPOINT`
is set. See [`observability.md`](observability.md).

## Flow

See the mermaid diagram in the top-level [`README.md`](../README.md) or
[`architecture.png`](architecture.png). In one line:

`request → Planner (Brief, + memory hint) → Caller ⇄ Supervisor on the live
call ⇄ Twilio ⇄ PSTN; Supervisor/Caller → escalation → your answer on the
dashboard → Caller resumes; hangup → Debrief (Scribe → DynamoDB + provider
memory + call_ended SSE).`
