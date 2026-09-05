# Holdline — Build Plan

Track: **Everyday Agents** · Deadline: **Sept 14, 2026 17:00 PT** · ~9.5 days, solo.

## What it is

A Strands voice agent that makes an outbound phone call to handle a task the user
dreads (primary vertical: **cancel a subscription and beat the retention offer**),
navigates the IVR, waits on hold, talks to the rep, and escalates to the user
mid-call — while holding the line — only when the rep pushes past the limits the
user set.

Nothing simulated: real PSTN call, real DTMF, real speech-to-speech, real hold
queue. The practice IVR is a test fixture, not a fake.

## Locked stack

| Layer | Choice |
|---|---|
| Voice core | Strands `BidiAgent` (`strands.experimental.bidi`) + Amazon Nova 2 Sonic (`BedrockNovaSonicModel`) |
| Telephony | Twilio Programmable Voice (outbound) + Twilio Media Streams WebSocket ↔ Nova Sonic |
| Multi-agent | Strands graph: **Planner** (text → Call Brief) → **CallSession** [ **Caller** ⇄ **Supervisor** ] → **Scribe** |
| Caller tools | `send_dtmf`, `escalate_to_user`, `lookup_task_context`, `record_outcome`, `end_call` |
| Deploy | AWS Bedrock AgentCore Runtime (bidi WebSocket; `awslabs/agentcore-samples` strands-ws harness as reference); AgentCore Memory for learned IVR paths. Local `uvicorn` kept as fallback. |
| State | DynamoDB: `tasks`, `calls`, `decisions` |
| Dashboard | FastAPI + plain HTML/JS: new-task form, live call view (transcript, hold timer, Decision card + countdown), history w/ recordings |

## Async blockers (start immediately)

1. AWS $50 credit form. 2. Bedrock Nova 2 Sonic model access (`us-east-1`).
3. AWS Builder ID. 4. Twilio trial + voice number. 5. GitHub repo (done: `chirag405/holdline`).

## Phases (day-by-day)

| Day | Goal | Proof |
|---|---|---|
| **1** | Repo scaffold + voice core spike (local mic) | 60s spoken convo with Nova Sonic; barge-in recovers; stub tool call fires |
| **2** | Twilio ⇄ Nova Sonic bridge *(highest risk)* | Real outbound call to own phone; two-way audio; latency ≤ ~1.5s; barge-in clean |
| **3** | DTMF + practice IVR + first happy path | Autonomous run: dial → DTMF menu → hold → rep → confirmation number → `record_outcome` |
| **4** | DynamoDB + Planner + Scribe | Request → Brief row; call → call row w/ transcript; Scribe extracts confirmation # |
| **5** | Supervisor + mid-call escalation *(money mechanic)* | Retention branch → Decision card, Caller stalls rep, user answers, Caller resumes & cancels; timeout path works |
| **6** | Dashboard | Whole seed scenario driven from the browser; decision answered in browser; history shows recording |
| **7** | Strands Graph wiring + AgentCore Runtime + Memory | 2nd call to same provider reuses remembered IVR path; AgentCore deploy handles a call (or fallback documented) |
| **8** | Hardening + error paths + tracing + seed scenarios | 3 scenarios pass back-to-back; deliberate call-drop → clean failure row; OTel trace screenshot |
| **9** | Submission assets | Fresh clone + README reproduces a practice-IVR call; arch diagram; ≤5-min video; MIT in About |
| **10** | Buffer + submit | One clean demo take; repo public; Devpost submitted |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Twilio Media Streams ↔ Nova Sonic latency/format eats days | High | Full day 2; unit-test resampling; fallback to Twilio `<Gather>`/`<Say>` scripted turns for the demo if the bridge stalls |
| `strands.experimental.bidi` API churns | Med | Pin exact versions; `MODEL_PROVIDER=nova_native` raw bedrock-runtime bidi path as fallback |
| DTMF can't be sent without tearing down the media stream | Med | Day 3 spike both methods (REST call-update vs. synthesized tones into the stream); practice IVR also accepts speech selection |
| Bedrock Nova 2 Sonic access not granted in time | Med | Request today; OpenAI Realtime is a same-interface Strands fallback for the voice core |
| AgentCore Runtime bidi deploy fiddly | Med | Local `uvicorn` is the demo path; AgentCore is the bonus |
| 5-min live demo flakes | Med | Record against deterministic practice IVR; one real call as a separate bonus clip |
| Two-party consent recording | Low | Practice IVR is self-owned; agent announces it's automated; recording off by default for third parties |
| Solo dev, 9.5 days | High | Days 2 & 5 are irreplaceable; Day 7 AgentCore, live link, blog post are droppable; Day 10 is buffer |

## Cost

Nova Sonic streaming + Twilio trial + ~$1–2 outbound + AgentCore + DynamoDB free tier ≈ **$5–10 total**.
