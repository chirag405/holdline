"""Config loads with sane defaults and derives table names correctly."""

from holdline.config import Settings, get_settings


def test_defaults_load(monkeypatch):
    for var in (
        "AWS_REGION",
        "MODEL_PROVIDER",
        "DDB_TABLE_PREFIX",
        "TWILIO_ACCOUNT_SID",
    ):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.aws_region == "us-east-1"
    assert s.model_provider == "nova_bidi"
    assert s.use_native_nova is False
    assert s.table("calls") == "holdline-calls"


def test_native_flag(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "nova_native")
    get_settings.cache_clear()
    s = get_settings()
    assert s.use_native_nova is True
    get_settings.cache_clear()


def test_table_prefix_override():
    s = Settings(
        aws_region="us-east-1",
        model_provider="nova_bidi",
        nova_sonic_model_id="x",
        nova_sonic_voice="matthew",
        twilio_account_sid="",
        twilio_auth_token="",
        twilio_from_number="",
        public_ws_url="",
        practice_ivr_number="",
        ddb_table_prefix="acme",
        agentcore_memory_id="",
        dashboard_host="127.0.0.1",
        dashboard_port=8000,
    )
    assert s.table("tasks") == "acme-tasks"
