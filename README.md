# Holdline

**The agent that holds the line so you don't have to.**

You hand Holdline a phone call you've been dreading — *"cancel my gym membership,
effective month-end, get me a confirmation number, don't accept a pause or a
downgrade."* It places a real phone call, fights through the phone tree, waits on
hold, talks to the representative, and interrupts you — mid-call, while it keeps
the line open — **only** when the rep pushes something outside the limits you set.

Built for the **Agents for Humans Hackathon** (Strands Agents SDK) — *Everyday
Agents* track.

> **Status:** in active development. See [`docs/plan.md`](docs/plan.md) for the
> day-by-day build plan and [`docs/architecture.md`](docs/architecture.md) for
> the design.

## Why this is hard (and why it's an agent, not a script)

A cancellation call is not a fixed script. The menu changes. You get transferred
to the wrong department. The retention rep is trained to not let you leave, and
whether their counter-offer is worth taking is a judgment call that belongs to
*you*, not the agent. Holdline runs the mechanical 95% autonomously and escalates
the 5% that is a real decision — without hanging up.

## Architecture at a glance

```
Plain-language request
        │
   Planner agent ──────────────►  Call Brief  (objective, identity info,
   (Strands, text)                             boundaries, success criteria)
        │
   CallSession (Strands graph node)
   ┌────────────────────────────────────────────────┐
   │  Caller agent            Supervisor agent        │
   │  BidiAgent + Nova 2 Sonic│  (Strands, text)       │
   │  live phone call    ◄────►  watches transcript,   │
   │  tools: send_dtmf,        │  forces escalate/abort │
   │  escalate_to_user, ...    │                        │
   └────────────────────────────────────────────────┘
        │                                   ▲
   Twilio Programmable Voice           Dashboard Decision card
   + Media Streams  ◄──► PSTN          (you answer, agent resumes)
        │
   Scribe agent → summary, confirmation number, follow-up
        │
   DynamoDB (tasks / calls / decisions) + AgentCore Memory (learned IVR paths)
```

Stack: **Strands Agents** (`BidiAgent`, multi-agent graph) · **Amazon Nova 2
Sonic** (speech-to-speech) · **Twilio** (outbound + Media Streams) · **AWS
Bedrock AgentCore Runtime + Memory** · **DynamoDB** · **FastAPI** dashboard.

## Setup

Requires Python 3.12, an AWS account with **Bedrock Nova 2 Sonic** model access
(`us-east-1`), and a Twilio account with a voice number.

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,mic]"
cp .env.example .env        # fill in AWS + Twilio values
```

Day-1 smoke test (local microphone, no phone call):

```bash
python scripts/voice_spike.py
```

Full setup and run instructions land in [`SETUP.md`](SETUP.md) as the pieces come
online.

## Ethics & consent

- Holdline **identifies itself as an automated assistant** calling on behalf of
  its user whenever asked, and at the start of a call where required.
- The primary demo target is a **practice IVR we operate ourselves**
  (`practice_ivr/`). It is a test fixture — every mechanism (real PSTN call, real
  DTMF, real speech-to-speech, real hold queue) is real, but no third party is
  contacted without consent.
- Call recording follows the stricter of the two parties' jurisdictions; it is
  **off by default** for any call to a number we do not control.

## License

[MIT](LICENSE) © 2026 Chirag Dhouni
