# Agents for Humans: building Holdline, an agent that waits on hold so you don't

> Draft for builder.aws.com. Title must contain "Agents for Humans". Publish
> publicly before the submission deadline. Split into 2–3 posts if you want the
> per-post bonus.

---

## The call you've been avoiding

I had "cancel gym membership" on my to-do list for three weeks. Not because it's
hard — because it's twenty-five minutes of hold music and a retention script.
That's the shape of task the Agents for Humans hackathon asks you to take on:
repetitive, judgment-heavy, and something a person actually dreads.

So I built **Holdline**: you give it the goal and your limits, it makes the
call — navigates the phone tree, waits on hold, talks to the rep — and it only
interrupts you, mid-call while it holds the line, when there's a real decision.

## Why this needed four agents, not a chatbot

- **Planner** (Strands `Agent` + structured output on Bedrock) turns "cancel my
  gym, don't accept a discount to stay" into a Call Brief with explicit
  `must_escalate` boundaries.
- **Caller** is a Strands `BidiAgent` running **Amazon Nova 2 Sonic** — real
  speech-to-speech, barge-in, tool calls mid-sentence — bridged to the phone
  network over a Twilio Media Stream.
- **Supervisor** (a text `Agent`) re-reads the transcript every few seconds
  against the Brief. If the Caller is about to agree to something it shouldn't,
  the Supervisor forces the pause.
- **Scribe** writes the call up afterwards and records what it learned — like the
  provider's menu path — so the next call is faster.

They're composed as a Strands `Graph`: `planner → call → debrief`, where the
`call` node runs the Caller and Supervisor concurrently on a shared transcript
bus.

## The AWS pieces

| Service | Role |
|---|---|
| Amazon Bedrock — **Nova 2 Sonic** | the live voice conversation |
| Amazon Bedrock — Nova Lite | the Planner / Supervisor / Scribe |
| Bedrock **AgentCore Memory** | learned IVR path + outcome per provider |
| Bedrock **AgentCore Runtime** | hosts the bidirectional WebSocket agent |
| DynamoDB | tasks, calls, decisions |
| Strands **OpenTelemetry** | one trace per call: planner, every Caller turn, each tool call, the Scribe |

## What was hard

- **The audio bridge.** Twilio speaks G.711 μ-law at 8 kHz; Strands/Nova speak
  linear PCM. Running Nova at `input_rate=output_rate=8000` meant the hot path
  needed zero resampling — a real latency win.
- **DTMF.** Twilio's Media Streams WebSocket has no "send a digit" message. The
  fix: synthesize the actual dual-tone signal as μ-law and inject it as audio, so
  the stream never tears down.
- **The human-in-the-loop, done right.** The escalation isn't a notification you
  read later — it's a tool the Caller calls that *blocks the call* (line still
  open, rep still there) until you answer on the dashboard, then returns your
  answer into the conversation. Timeout falls back to a safe default from the
  Brief.
- **Failure paths.** No-answer, a dropped stream, a rejected keypress, a Bedrock
  hiccup — every one had to become a recorded outcome, never a call stuck
  forever.

## Nothing simulated

The demo target is a practice IVR I host myself — a test fixture, not a fake
business — but every mechanism is real: a real PSTN call, real touch-tones, real
speech-to-speech, a real hold queue, a real retention conversation. Point it at a
real number and the agent behaves identically.

## Try it

Code: https://github.com/chirag405/holdline — `pytest` and the full dashboard run
with no accounts; a live call needs Bedrock + Twilio.
