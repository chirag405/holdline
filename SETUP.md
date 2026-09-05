# Holdline — Setup

Growing document. Right now it covers Day 1 (voice core spike). Telephony,
dashboard, and AgentCore sections are added as those milestones land.

## Prerequisites

| Need | Notes |
|---|---|
| Python **3.12** | Not 3.13 — the stdlib `audioop` module (used for μ-law audio) was removed there. |
| AWS account | With **Amazon Bedrock Nova 2 Sonic** model access enabled in your region (`us-east-1` recommended). Request it in the Bedrock console → Model access. |
| AWS credentials | Standard chain: env vars, SSO, or `~/.aws/credentials`. |
| Twilio account | Trial is fine. One voice-capable phone number. *(Day 2+)* |
| A microphone | For the Day 1 local spike only. |

## Install

```bash
git clone https://github.com/chirag405/holdline.git
cd holdline
python -m venv .venv
. .venv/Scripts/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev,mic]"
cp .env.example .env
```

Fill in `.env`:

- `AWS_REGION` — where you have Nova 2 Sonic access.
- Leave `MODEL_PROVIDER=nova_bidi` for now.
- Twilio values can stay blank until Day 2.

## Day 1 smoke test — local microphone, no phone call

```bash
python scripts/voice_spike.py
```

Speak into your mic: *"Hi, I'm calling to cancel my gym membership."*
The agent should reply in voice, and you should be able to talk over it (barge-in).
Say *"okay, we're done here"* and it should call the `end_call` tool and exit.
Ctrl+C stops it any time.

If `BedrockNovaSonicModel` fails to construct, check that your AWS creds resolve
(`aws sts get-caller-identity`) and that Nova 2 Sonic model access is granted in
`AWS_REGION`.

## Day 2 — the Twilio ↔ Nova Sonic bridge (real outbound call)

Extra prerequisites:

- **Twilio account** + a voice-capable number. Put `TWILIO_ACCOUNT_SID`,
  `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` in `.env`.
- A **public tunnel** to your laptop so Twilio can reach the bridge:

  ```bash
  cloudflared tunnel --url http://localhost:8000      # or: ngrok http 8000
  ```

  Copy the `https://…` URL it prints into `.env` as `PUBLIC_WS_URL`
  (the bridge rewrites it to `wss://…/ts` for the media stream).

Run it:

```bash
python scripts/run_bridge.py                 # terminal 1: the bridge
python scripts/place_call.py +1YOURCELL      # terminal 2: dial yourself
```

Your phone rings; answer it and talk. The agent (Holdline) should greet you,
hear you, and you should be able to talk over it (barge-in cuts its audio).
Say the cancellation is done with a confirmation number and it wraps up.

What to check: two-way audio, round-trip latency around a second or less, and
no audio artifacts. Logs stream in terminal 1 (`transcript`, `twilio.*`).

### How it fits together

```
scripts/place_call.py ──POST /calls──► bridge ──Twilio REST──► outbound call
                                                     │
                          Twilio fetches  GET /twiml ◄┘  ──► <Connect><Stream wss://…/ts>
                                                     │
   phone audio ◄──── Twilio Media Streams WS ───► WS /ts ──► TwilioMediaStream
                                                              │  (mu-law 8k ⇄ PCM 8k)
                                                              ▼
                                                    BidiAgent + Nova 2 Sonic
```

## Day 3 — the practice IVR + first autonomous run

The practice IVR (`src/holdline/practice/ivr.py`) is served by the same bridge.
See [`practice_ivr/README.md`](practice_ivr/README.md) for the full flow.

1. Take a **second** Twilio number (keep the first as Holdline's caller ID). Set
   its **Voice → "A call comes in"** webhook to `https://<tunnel>/practice/entry`
   (HTTP POST). Put the number in `.env` as `PRACTICE_IVR_NUMBER`.
2. With the bridge + tunnel running:

   ```bash
   python scripts/place_call.py $env:PRACTICE_IVR_NUMBER    # PowerShell
   ```

Holdline dials the practice line, presses/says its way through the menu
(`2` → `4`), waits silently on hold, greets the rep, declines the retention
offer, and captures the `IPF######` confirmation number. The bridge logs it:

```
ws.done  outcome=cancelled  confirmation_number=IPF473921
```

Offline check (no telephony/AWS — walks the IVR the way Twilio would):

```bash
python scripts/verify_day3.py
```

## Day 4 — state, Planner, Scribe

**State backend.** `STATE_BACKEND=memory` (in `.env`) keeps everything in-process —
good for local dev and the offline checks. `STATE_BACKEND=dynamodb` (default) needs
AWS and the tables:

```bash
python scripts/create_tables.py     # creates holdline-tasks / -calls / -decisions (on-demand)
```

**Planner + Scribe** are text agents on Bedrock (`TEXT_MODEL_ID`, default
`us.amazon.nova-lite-v1:0`). Try the Planner on its own:

```bash
python scripts/plan_demo.py "Cancel my Iron Peak Fitness gym membership, effective end of the month. Get a confirmation number. Don't accept a pause or a discount."
```

It prints the structured **Call Brief** and the rendered Caller instructions.

**End to end**, once the bridge + tunnel are up:

```bash
# plan a task, then call the practice line with it
curl -s localhost:8000/tasks -H 'content-type: application/json' \
  -d '{"request":"Cancel my Iron Peak Fitness membership","fields":{"account_number":"IPF-99123"}}'
# -> {"task_id":"task_...","brief":{...}}
python scripts/place_call.py $env:PRACTICE_IVR_NUMBER   # then POST /calls with that task_id
```

`POST /calls` accepts `{"to","task_id"}` (preferred), `{"to","request"}` (plans
inline), or `{"to","goal"}` (raw passthrough). After the call, the **Scribe**
writes a summary + confirmation number to the `calls` row and closes the task.

Offline check:

```bash
python scripts/verify_day4.py
```

## Day 5 — Supervisor + mid-call escalation

Two things now watch the call:

- The **Caller** is told to call `escalate_to_user` itself the moment the rep
  raises anything on the Brief's `must_escalate` list (a retention offer, a fee,
  a plan change). It says a holding phrase to the rep and the tool blocks — the
  line stays open — until the account holder answers.
- The **Supervisor** (`SUPERVISOR_ENABLED=true`) is a text agent that re-reads the
  transcript every `SUPERVISOR_INTERVAL_S` seconds against the Brief. If the Caller
  misses a boundary, the Supervisor forces the pause itself.

Either way an escalation becomes a `decisions` row. Answer it while the call holds:

```bash
python scripts/answer_decision.py                        # list pending
python scripts/answer_decision.py <decision_id> "hold firm"
```

(or `GET /decisions` and `POST /decisions/{id}` directly). No answer within
`ESCALATION_TIMEOUT_S` → the call falls back to the Brief's `default_on_timeout`.

Demo: place the practice-line call with a task whose Brief forbids retention
offers. When "Jordan" offers 3 months at 50%, the Caller stalls, a decision
appears, you answer `hold firm`, and the Caller resumes and secures the
cancellation.

Offline check:

```bash
python scripts/verify_day5.py
```

## Day 6 — the dashboard (Next.js)

The backend gained a dashboard-facing API: `GET /config`, `GET /calls`,
`GET /calls/{id}`, `GET /tasks/{id}`, and `GET /stream` (Server-Sent Events —
`turn`, `status`, `decision_open`, `decision_resolved`, `call_ended`). CORS is
open in dev.

The dashboard itself is a separate **Next.js** app in `frontend/`, built entirely
from shadcn-registry components (Watermelon UI, prompt-kit, Motion Primitives,
Aceternity).

```bash
# terminal 1 — backend (memory backend needs no AWS/Twilio to show the shell)
STATE_BACKEND=memory python scripts/run_bridge.py

# terminal 2 — dashboard
cd frontend
npm install
cp .env.local.example .env.local     # NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev                          # http://localhost:3000
```

The page: plan a call on the left, watch it run on the right — streaming
transcript, a live hold timer, and the **Decision card** (question + option
buttons + countdown) when Holdline needs your call. Past calls, with transcript
and confirmation number, are listed below and at `/calls/{id}`.

## Day 7 — Strands Graph + provider memory + AgentCore

**Strands Graph.** Each call now runs through a `Graph` (`holdline/graph.py`):
`planner → call → debrief`. The `call` node is the live Caller + Supervisor
session; the `debrief` node runs the Scribe, updates provider memory, and emits
`call_ended`. Set `USE_GRAPH=false` to call the same steps directly instead.

**Provider memory** (`MEMORY_BACKEND`):

- `local` (default) — in-process, seeded with the practice line's menu path.
  Durable for the life of the bridge process.
- `agentcore` — Amazon Bedrock AgentCore Memory (`pip install -e ".[agentcore]"`,
  optionally set `AGENTCORE_MEMORY_ID`). One event per call under session id
  `provider:<slug>`; durable across runs.

Either way: the Planner reads a provider's known IVR path before the call, the
Scribe writes the path + outcome back after. The **second** call to the same
provider starts already knowing the menu.

**AgentCore Runtime** (optional deploy): `deploy/agentcore/` — a
`BedrockAgentCoreApp` that mounts the bridge, a Dockerfile, and step-by-step
instructions. The local `uvicorn` path (`scripts/run_bridge.py`) is unchanged and
is the tested one.

Offline check:

```bash
python scripts/verify_day7.py
```

## Day 8 — hardening + tracing + the demo scenarios

**Error paths** now all land as a recorded outcome, never a hang:

| failure | becomes |
|---|---|
| no-answer / busy / failed / canceled (Twilio `/call-status` webhook) | `calls` row `outcome=no_answer` (etc.), task `failed` |
| media stream drops mid-call | debrief runs the Scribe on the partial transcript |
| Nova stream error before anything happens | `calls` row `outcome=error`, no Scribe pass |
| DTMF tones don't register | `press_keys` tells the Caller to say the digits instead |
| transferred in circles / wrong department | Supervisor `abort` → Caller wraps up with `record_outcome("failed")` |
| Planner (Bedrock) fails | degrades to a plain brief from the request; the call still runs |

**Tracing**: Strands OpenTelemetry is on by default. `TRACING_CONSOLE=true` prints
spans; set `OTEL_EXPORTER_OTLP_ENDPOINT` to send them to Jaeger / Tempo / X-Ray.
See [`docs/observability.md`](docs/observability.md).

**The three demo scenarios** (needs the full live stack + `PRACTICE_IVR_NUMBER`):

```bash
python scripts/seed_scenarios.py        # a: clean cancel · b: retention→hold firm · c: escalation→accept
```

Offline check (scenarios via the practice IVR TwiML, error paths, telemetry):

```bash
python scripts/verify_day8.py
```

## Run the tests

```bash
pytest -q
```
