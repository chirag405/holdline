# Devpost submission checklist

Track: **Everyday Agents**. Deadline: **Sept 14, 2026, 17:00 PT** (Devpost rules).

## Required

| Item | Status | Notes |
|---|---|---|
| New AI agent built with Strands Agents SDK | ✅ | 4 agents (Planner / Caller / Supervisor / Scribe) + a Strands `Graph`; `BidiAgent` on Nova 2 Sonic |
| Handles a real task end to end | ✅ | places a real PSTN call, navigates the IVR, holds, negotiates, records the outcome |
| Public code repo | ✅ | https://github.com/chirag405/holdline |
| Source + assets + setup instructions | ✅ | [`README.md`](../README.md), [`SETUP.md`](../SETUP.md), `.env.example`, `deploy/agentcore/` |
| MIT or Apache license, visible in About | ✅ | [`LICENSE`](../LICENSE) (MIT) at repo root — GitHub shows it in the About panel |
| README | ✅ | [`README.md`](../README.md) |
| Architecture diagram | ✅ | mermaid in the README + [`architecture.png`](architecture.png) / [`architecture.mmd`](architecture.mmd) |
| Demo video ≤ 5 min (working demo + problem/audience/why) | ☐ **you** | script: [`demo-script.md`](demo-script.md). Record, upload to YouTube/Vimeo, set public |
| AWS Builder ID | ☐ **you** | create at https://profile.aws.amazon.com if you don't have one; paste into the Devpost form |
| Text description (what / who / how) | ☐ **you** | reuse the top of the README |

## Optional (score higher)

| Item | Status |
|---|---|
| Live demo link | ☐ deploy the dashboard (Vercel) + bridge (AgentCore Runtime or a small box) and add the URL. `deploy/agentcore/README.md` has the steps. |
| AgentCore Runtime deployment | ☐ `deploy/agentcore/` — configure + launch |
| builder.aws.com blog post ("Agents for Humans" in the title) | ☐ draft at [`blog-draft.md`](blog-draft.md); publish publicly before the deadline (up to 3, +0.2 each) |

## What a judge can run without any accounts

```bash
pip install -e ".[dev]" && pytest -q          # 55 tests
python scripts/verify_day8.py                  # offline end-to-end
STATE_BACKEND=memory python scripts/run_bridge.py
cd frontend && npm i && npm run dev            # full dashboard against the in-process backend
```

A live call additionally needs AWS Bedrock (Nova 2 Sonic) + Twilio, per
`SETUP.md`.
