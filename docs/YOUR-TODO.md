# Holdline — your turn: a step-by-step runbook

Everything the code can do is built and tested. This file is the list of things
**only you** can do — accounts, credentials, a real call, the video, the Devpost
form — in the order to do them.

Work top to bottom. Each step has a "done when" so you know it worked.
Commands are PowerShell (your machine); run them from `C:\dev\holdline` unless
told otherwise.

- [ ] 1. Accounts & access
- [ ] 2. Fill in `.env`
- [ ] 3. Prove it runs with no accounts
- [ ] 4. First real voice test (microphone only)
- [ ] 5. Bring up the full live stack
- [ ] 6. Run the three demo scenarios
- [ ] 7. (optional) Deploy for a live-demo link
- [ ] 8. Record the demo video
- [ ] 9. (optional) Publish the builder.aws.com post
- [ ] 10. Submit on Devpost

---

## 1. Accounts & access

- [ ] **AWS account** — https://aws.amazon.com if you don't have one.
- [ ] **Bedrock model access** — AWS console → **Amazon Bedrock** → *Model
  access* → **Request** these, in region **us-east-1**:
  - `Amazon Nova 2 Sonic` (the voice model — required)
  - `Amazon Nova Lite` (the Planner/Supervisor/Scribe — required)
  - Approval is usually instant; occasionally a few hours.
- [ ] **AWS credentials on this machine** — easiest:
  ```powershell
  aws configure          # paste an access key + secret, region us-east-1
  ```
  (or put `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `.env` — step 2.)
  **Done when:** `aws sts get-caller-identity` prints your account.
- [ ] **$50 AWS credits** (hackathon) — form: https://forms.gle/6sjzKiX6bKUMA5NEA
  — **deadline Sept 11, 12:00 PT**. Credits expire Oct 31.
- [ ] **AWS Builder ID** — https://profile.aws.amazon.com → sign in / create.
  Copy the ID; you paste it into the Devpost form in step 10.
- [ ] **Twilio account** — https://www.twilio.com/try-twilio (trial is fine).
  - From the Console dashboard, copy **Account SID** and **Auth Token**.
  - **Buy two phone numbers** (Console → Phone Numbers → Buy a number,
    Voice capability): one is Holdline's caller ID, one is the practice line.
    Trial accounts: a trial number can only call *verified* numbers — verify
    your own cell and the practice number under *Verified Caller IDs*, or
    upgrade with a small top-up.

## 2. Fill in `.env`

```powershell
copy .env.example .env
notepad .env
```

Fill these (leave the rest at defaults):

| var | value |
|---|---|
| `AWS_REGION` | `us-east-1` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | only if you did **not** run `aws configure` |
| `TWILIO_ACCOUNT_SID` | from the Twilio console |
| `TWILIO_AUTH_TOKEN` | from the Twilio console |
| `TWILIO_FROM_NUMBER` | your **first** Twilio number, `+1…` format |
| `PRACTICE_IVR_NUMBER` | your **second** Twilio number, `+1…` |
| `PUBLIC_WS_URL` | leave blank for now — you set it in step 5 |

Keep `STATE_BACKEND=memory` and `MEMORY_BACKEND=local` for the demo (no DynamoDB
needed). To use DynamoDB instead: set `STATE_BACKEND=dynamodb` and run
`python scripts/create_tables.py` once. For durable AgentCore memory set
`MEMORY_BACKEND=agentcore` and `pip install -e ".[agentcore]"`.

**Done when:** `.env` exists with the Twilio + AWS values filled in.

## 3. Prove it runs with no accounts

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,mic]"
pytest -q                      # expect: 55 passed
python scripts/verify_day8.py  # expect: DAY 8 VERIFY: PASS
```

**Done when:** tests pass and the verify script says PASS.

## 4. First real voice test (microphone only)

No phone call yet — this proves AWS Bedrock + Nova 2 Sonic work.

```powershell
python scripts/voice_spike.py
```

Speak: *"Hi, I'm calling to cancel my gym membership."* Talk over it (it should
stop). Say *"okay, we're done here"* — it should hang up.

**Done when:** you have a back-and-forth spoken conversation.
**If it errors:** re-check `aws sts get-caller-identity` and that **Nova 2 Sonic**
model access is *granted* in `us-east-1`.

## 5. Bring up the full live stack

Three terminals (all with the venv activated where relevant).

**Terminal A — the bridge:**
```powershell
python scripts/run_bridge.py            # http://localhost:8000
```

**Terminal B — a public tunnel** (install cloudflared: `winget install --id Cloudflare.cloudflared`):
```powershell
cloudflared tunnel --url http://localhost:8000
```
Copy the `https://xxxxx.trycloudflare.com` URL it prints. Put it in `.env` as
`PUBLIC_WS_URL`, then **restart Terminal A** so it picks up the change.

**Point the practice number at the tunnel:** Twilio Console → Phone Numbers →
your **second** number → *Voice Configuration* → **A call comes in** → *Webhook*
→ `https://xxxxx.trycloudflare.com/practice/entry` → HTTP **POST** → Save.

**Terminal C — the dashboard:**
```powershell
cd frontend
npm install
copy .env.local.example .env.local
npm run dev                            # http://localhost:3000
```

**Smoke test the call path:**
```powershell
python scripts/place_call.py $env:PRACTICE_IVR_NUMBER
```
Watch Terminal A: you should see `twilio.start`, transcript lines, DTMF, then a
result. The dashboard's Live panel should stream the same thing.

**Done when:** a call to the practice number runs start-to-finish and the
dashboard shows the transcript + a confirmation number.

## 6. Run the three demo scenarios

With the stack from step 5 up:

```powershell
python scripts/seed_scenarios.py            # all three
python scripts/seed_scenarios.py b          # just scenario b
```

- **a** — clean auto-cancel (the agent declines the retention offer itself)
- **b** — retention → you answer the Decision card **"Hold firm on the original request"**
- **c** — escalation → you answer **"Accept the offer"** (agent keeps the membership)

For **b** and **c** the script waits and answers the decision for you; you can
also click the button on the dashboard instead.

**Done when:** all three print an outcome + (for a/b) a confirmation number.

## 7. (optional) Deploy for a live-demo link

Scores higher on Technical Implementation. Two parts:

- **Dashboard → Vercel:** `cd frontend`, push to GitHub (already done), import
  the `frontend/` dir at vercel.com, set `NEXT_PUBLIC_API_BASE` to your bridge's
  public URL.
- **Bridge → AgentCore Runtime:** follow
  [`deploy/agentcore/README.md`](../deploy/agentcore/README.md)
  (`agentcore configure` → `agentcore launch`), then set `PUBLIC_WS_URL` to the
  runtime endpoint + `/holdline`.

If the deploy fights you, skip it — the local stack + a screen recording is a
valid submission.

## 8. Record the demo video (≤ 5:00, required)

Follow [`demo-script.md`](demo-script.md) shot for shot. Record against the
**practice IVR** (deterministic). Screen + voiceover is fine; no camera.

Must include: (1) the problem, (2) who it's for, (3) why it matters, and a
working end-to-end run.

- [ ] Record with the stack from step 5 running, browser at `localhost:3000`.
- [ ] Upload to **YouTube or Vimeo**, set visibility **Public** (not Unlisted).
- [ ] Copy the URL for the Devpost form.

## 9. (optional) Publish the builder.aws.com post

Draft: [`blog-draft.md`](blog-draft.md). Title **must contain "Agents for
Humans"**. Publish publicly on builder.aws.com **before the deadline**. Up to 3
posts, +0.2 each.

## 10. Submit on Devpost

Go to https://agentsforhumans.devpost.com → **Submit a project**. Fields:

| field | what to put |
|---|---|
| Project name | Holdline |
| Track | **Everyday Agents** |
| Text description | the top of [`README.md`](../README.md) (what / who / how) |
| Repo URL | `https://github.com/chirag405/holdline` (make sure it's **public**) |
| Architecture diagram | `docs/architecture.png` (upload) — it's also in the README |
| Demo video URL | from step 8 |
| AWS Builder ID | from step 1 |
| Live demo link | from step 7, if you did it |
| Blog post link(s) | from step 9, if you did it |

- [ ] Repo is **public** and the MIT `LICENSE` shows in the GitHub "About" panel.
- [ ] Submit **before Sept 14, 17:00 PT** (Devpost rules time).

Full checklist with status: [`submission.md`](submission.md).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `voice_spike.py` → credentials / access error | `aws sts get-caller-identity`; Bedrock → Model access → Nova 2 Sonic **granted** in `us-east-1` |
| `POST /calls` → `PUBLIC_WS_URL not set` | set it in `.env` from the tunnel, **restart the bridge** |
| Call connects but silence both ways | tunnel down, or `PUBLIC_WS_URL` is `http://` not the `https://` the tunnel gave you |
| Practice number rings but no menu | its Voice webhook isn't `https://<tunnel>/practice/entry` (POST) |
| Twilio trial: "number not verified" | verify the target under Console → Verified Caller IDs, or upgrade the account |
| Dashboard shows nothing live | bridge not running on `:8000`, or `NEXT_PUBLIC_API_BASE` in `frontend/.env.local` is wrong |
| DTMF not registering on the IVR | expected sometimes — the agent falls back to *saying* the digits; the practice IVR accepts both |
| Want traces for the video | `TRACING_CONSOLE=true` in `.env`, or run Jaeger — see [`observability.md`](observability.md) |
