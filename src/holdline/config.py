"""Central configuration, loaded once from the environment (.env in dev).

Everything the agents, telephony bridge, and dashboard need is read here so the
rest of the code never touches os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            f"Copy .env.example to .env and fill it in."
        )
    return val


@dataclass(frozen=True)
class Settings:
    # AWS / Bedrock
    aws_region: str
    model_provider: str  # "nova_bidi" | "nova_native"
    nova_sonic_model_id: str
    nova_sonic_voice: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    public_ws_url: str
    practice_ivr_number: str

    # State
    ddb_table_prefix: str
    agentcore_memory_id: str

    # Dashboard
    dashboard_host: str
    dashboard_port: int

    def table(self, name: str) -> str:
        """DynamoDB table name for a logical table (tasks / calls / decisions)."""
        return f"{self.ddb_table_prefix}-{name}"

    @property
    def use_native_nova(self) -> bool:
        return self.model_provider == "nova_native"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        model_provider=os.environ.get("MODEL_PROVIDER", "nova_bidi"),
        nova_sonic_model_id=os.environ.get(
            "NOVA_SONIC_MODEL_ID", "amazon.nova-2-sonic-v1:0"
        ),
        nova_sonic_voice=os.environ.get("NOVA_SONIC_VOICE", "matthew"),
        twilio_account_sid=os.environ.get("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
        twilio_from_number=os.environ.get("TWILIO_FROM_NUMBER", ""),
        public_ws_url=os.environ.get("PUBLIC_WS_URL", ""),
        practice_ivr_number=os.environ.get("PRACTICE_IVR_NUMBER", ""),
        ddb_table_prefix=os.environ.get("DDB_TABLE_PREFIX", "holdline"),
        agentcore_memory_id=os.environ.get("AGENTCORE_MEMORY_ID", ""),
        dashboard_host=os.environ.get("DASHBOARD_HOST", "127.0.0.1"),
        dashboard_port=int(os.environ.get("DASHBOARD_PORT", "8000")),
    )


__all__ = ["Settings", "get_settings"]
