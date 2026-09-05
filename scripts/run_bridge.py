"""Start the Holdline telephony bridge (FastAPI + WebSocket)."""

from __future__ import annotations

import uvicorn

from holdline.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    uvicorn.run(
        "holdline.telephony.bridge:app",
        host=s.dashboard_host,
        port=s.dashboard_port,
        reload=False,
        log_level="info",
    )
