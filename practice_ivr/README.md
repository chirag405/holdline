# Practice IVR

A self-hosted phone line that behaves like a real gym-membership cancellation
desk: a touch-tone menu, a hold queue, and a retention representative who offers a
discount before processing the cancellation and reading back a confirmation
number.

**It is a test fixture, not a fake business.** Holdline dials it exactly as it
would dial a real number. Every mechanism it exercises is real — a PSTN call,
IVR menus, DTMF, time spent on hold, and an unscripted-feeling retention
conversation. Nothing about the *agent's* behaviour is simulated.

## Why self-hosted (instead of a Twilio Studio flow)

- The whole fixture lives in the repo (`src/holdline/practice/ivr.py`), so anyone
  can reproduce the demo from a clean clone — no console flow to import.
- It is version-controlled and unit-tested (`tests/test_practice_ivr.py`).

## How to use it

1. Run the bridge (`python scripts/run_bridge.py`) and expose it with a tunnel —
   the practice IVR endpoints ride on the same server as the Holdline bridge.
2. In the Twilio console, take a **second** phone number (keep your first number
   as Holdline's caller ID) and set its **Voice → "A call comes in"** webhook to:

   ```
   https://<your-tunnel-domain>/practice/entry      (HTTP POST)
   ```

3. Put that number in `.env` as `PRACTICE_IVR_NUMBER`.
4. Place the call:

   ```bash
   python scripts/place_call.py $PRACTICE_IVR_NUMBER
   ```

   Holdline calls the practice line, works through the menu, waits on hold, talks
   the rep out of the retention offer, and records the confirmation number.

## Call flow

| Endpoint | Behaviour |
|---|---|
| `/practice/entry` | Greeting + main menu. `2` / "membership" → membership submenu. |
| `/practice/menu` | Routes the main-menu choice. |
| `/practice/membership` | `4` / "cancel" → hold queue (~15–20 s with hold music) → rep. |
| `/practice/rep_intro` | "This is Jordan in member services. How can I help?" |
| `/practice/rep` | First cancel request → **retention offer** (3 months at 50%). A "no" → cancels and reads an `IPF######` confirmation number. A "yes" → applies the discount (the branch Day 5's escalation demo uses). |
| `/practice/rep_close` | Goodbye / hangup. |

The menu `<Gather>`s accept **both DTMF and speech**, so the demo still works if
injected touch-tones don't register on a given carrier path — the agent just says
the number instead.
