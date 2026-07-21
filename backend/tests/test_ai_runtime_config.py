import json

from app.ai.runtime_config import (
    AIRuntimeConfig,
    parse_database_config,
    serialize_database_config,
)
from app.config import settings


def test_database_ai_config_encrypts_and_round_trips_api_key(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET", "runtime-config-test-secret")
    config = AIRuntimeConfig(
        enabled=True,
        api_key="provider-secret-key",
        base_url="https://provider.example/v1",
        model="provider-model",
        moderation_provider_fallback_enabled=True,
        source="database",
    )

    serialized = serialize_database_config(config)
    payload = json.loads(serialized)

    assert "provider-secret-key" not in serialized
    assert payload["api_key"]
    assert parse_database_config(serialized) == config


def test_database_ai_config_rejects_unreadable_ciphertext(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET", "runtime-config-test-secret")
    serialized = json.dumps(
        {
            "version": 1,
            "enabled": True,
            "api_key": "not-valid-fernet-data",
            "base_url": "https://provider.example/v1",
            "model": "provider-model",
            "moderation_provider_fallback_enabled": True,
        }
    )

    assert parse_database_config(serialized) is None
