"""AgentCore Runtime entrypoint.

Wraps the Holdline bridge (FastAPI: WS /ts, /twiml, /calls, /stream, /decisions,
/practice/*) in a `BedrockAgentCoreApp` so it can run on Amazon Bedrock AgentCore
Runtime, which supports the bidirectional WebSocket the Nova Sonic Caller needs.

The bridge is mounted under /holdline, so once deployed set:

    PUBLIC_WS_URL = wss://<your-agentcore-runtime-endpoint>/holdline

Local runs still use `python scripts/run_bridge.py` (plain uvicorn) unchanged.
"""

from __future__ import annotations

from bedrock_agentcore import BedrockAgentCoreApp

from holdline.telephony.bridge import app as holdline_app

app = BedrockAgentCoreApp()
app.mount("/holdline", holdline_app)


@app.ping
def ping() -> str:
    return "healthy"


if __name__ == "__main__":
    app.run()
