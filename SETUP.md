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

## Run the tests

```bash
pytest -q
```
