# Deploying Holdline on Amazon Bedrock AgentCore Runtime

AgentCore Runtime supports the bidirectional WebSocket the Nova Sonic Caller
needs, and pairs with **AgentCore Memory** (`MEMORY_BACKEND=agentcore`) for the
learned-IVR-path memory. Deploying here strengthens the Technical Implementation
score, but it is **optional** — the local path below is the tested one and the
demo runs on it.

## What runs where

| | Local (tested) | AgentCore Runtime |
|---|---|---|
| Host | `python scripts/run_bridge.py` (uvicorn) | container from `deploy/agentcore/Dockerfile` |
| Entrypoint | `holdline.telephony.bridge:app` | `deploy/agentcore/app.py` (`BedrockAgentCoreApp` mounting the bridge at `/holdline`) |
| Public URL for Twilio | an ngrok / cloudflared tunnel | the AgentCore Runtime endpoint |
| State / Memory | `memory` / `local` | `dynamodb` / `agentcore` |

## Steps

1. **Prereqs**: AWS account with Bedrock model access (Nova 2 Sonic + the text
   model), an execution role for AgentCore, Docker, and the AgentCore CLI:

   ```bash
   pip install bedrock-agentcore-starter-toolkit
   python scripts/create_tables.py            # DynamoDB tables
   ```

2. **Configure** (from the repo root — the Dockerfile expects that build context):

   ```bash
   agentcore configure \
     --entrypoint deploy/agentcore/app.py \
     --container-runtime docker \
     --dockerfile deploy/agentcore/Dockerfile \
     --name holdline
   ```

3. **Set runtime environment** (via the CLI prompts or the console): everything
   from `.env` that isn't a local-only value — `AWS_REGION`, `TWILIO_*`,
   `TEXT_MODEL_ID`, `NOVA_SONIC_*`, `STATE_BACKEND=dynamodb`,
   `MEMORY_BACKEND=agentcore`, and `AGENTCORE_MEMORY_ID` (create one first with
   `MemoryClient().create_or_get_memory(name="holdline_provider_memory")`, or
   leave blank to auto-create on first use).

4. **Launch**:

   ```bash
   agentcore launch
   ```

   Note the runtime endpoint it prints.

5. **Point Twilio at it**: set `PUBLIC_WS_URL=wss://<endpoint>/holdline` wherever
   you call `POST /calls` from (the dashboard's backend, or `scripts/place_call.py`).
   The bridge derives `/holdline/twiml` and `wss://…/holdline/ts` from that base.

## Fallback

If the deploy is blocked (IAM, ECR, quota, or the bidi-WebSocket path on the
runtime), run the local bridge + a tunnel exactly as in `SETUP.md`. Nothing in
the agent code changes — only where the container runs.
