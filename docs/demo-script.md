# Demo video script (≤ 5:00)

Screen recording + voiceover. No face needed. Record against the **practice IVR**
(deterministic, reproducible); keep one real opt-in call as a bonus clip if you
want.

**Setup before recording:** bridge + tunnel + dashboard running, `.env` filled,
practice number's voice webhook at `<tunnel>/practice/entry`, `TRACING_CONSOLE`
off, browser at `http://localhost:3000`, a terminal showing the bridge log.

---

## 0:00–0:35 — The problem

> "Everyone has a phone call rotting on their to-do list. Cancel the gym. Dispute
> a bill. It's not hard — it's twenty-five minutes of hold music, a menu that
> changes, and a rep whose job is to not let you leave. And it's worse if phone
> calls are a barrier for you — anxiety, a second language, no spare time."

Show a sticky note / to-do list with "☎ cancel gym" crossed-forward three weeks.

## 0:35–1:05 — What Holdline is

> "Holdline is a Strands agent that makes the call for you. You tell it the goal
> and your limits. It dials, works the menu, waits on hold, talks to the rep —
> and it only interrupts you, mid-call while it holds the line, when there's a
> real decision to make."

Dashboard hero on screen. Type into the form:

> *Cancel my Iron Peak Fitness membership, effective end of the billing period.
> Get a confirmation number. Don't accept a pause, downgrade, or discount to
> stay.*

Click **Plan the call**. The Call Brief appears — read the "Will ask you before
agreeing to: any retention offer" line aloud.

## 1:05–3:20 — The call, live

Click **Place the call**. Narrate over the live panel:

- **0:00** status flips to *Dialing* → *On the call*. Hold timer starts.
- Transcript streams: the IVR greeting, then *Holdline* → `press_keys("2")` →
  `press_keys("4")`. > "It's sending real touch-tones down the line."
- *"All our specialists are helping other members, please hold."* Hold music.
  Timer ticks. > "It just waits. Silently."
- Rep picks up: *"This is Jordan in member services."* Holdline states it's an
  automated assistant for the account holder and asks to cancel.
- Rep: *"Before I do that — three months at fifty percent off if you stay?"*
- **The Decision card appears.** Status → *Waiting on you*. Countdown bar.
  Holdline audibly stalls the rep: *"Let me check with the account holder, can
  you hold a moment?"*
  > "This is the whole point. That counter-offer isn't Holdline's call to make."
- Click **Hold firm on the original request**.
- Holdline resumes: declines, insists. Rep: *"Okay, you're cancelled effective
  end of period. Confirmation number I-P-F-…"*
- Holdline: `record_outcome("cancelled", "IPF……")`, brief goodbye, hangs up.

Status → *Call ended*, green check, `confirmation IPF……`.

## 3:20–4:00 — After the call

- Scroll to **Recent calls** → open the call. Show the full transcript, the
  outcome, the confirmation number, and the follow-up draft ("verify no charge
  on next statement").
- > "The Scribe also wrote this provider's menu path to memory. The next call to
  > Iron Peak starts already knowing to press 2 then 4."
- (Optional) flip to the terminal / Jaeger: one trace per call, spans for the
  planner, each Caller turn, the `escalate_to_user` tool, the Supervisor, the
  Scribe.

## 4:00–4:45 — How it's built

Architecture diagram on screen.

> "Four Strands agents. The **Planner** turns your request into a structured
> brief with hard boundaries. The **Caller** is a Strands `BidiAgent` on Amazon
> Nova 2 Sonic — real speech-to-speech over a Twilio Media Stream. A
> **Supervisor** agent watches the transcript and forces the pause if the Caller
> misses a boundary. The **Scribe** writes it all up. It's wired as a Strands
> `Graph` — planner, call, debrief — with DynamoDB for state and AgentCore
> Memory for what it learns. Every failure path — no answer, dropped call, a
> rejected keypress — lands as a clean recorded outcome, never a hang."

## 4:45–5:00 — Close

> "The mechanical work is done for you. Holdline only asks when the answer is
> actually yours. That's the busywork gone — and the decision kept."

Repo URL on screen.
