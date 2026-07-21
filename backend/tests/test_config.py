import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_weak_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="change-me-in-production",
        )


def test_development_allows_local_compose_secret():
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        JWT_SECRET="change-me-in-production",
        DEPLOY_ENABLED=False,
        GITHUB_REPO="",
    )

    assert settings.DEPLOY_ENABLED is False


def test_production_accepts_strong_jwt_secret():
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        JWT_SECRET="a-unique-production-secret-with-32-characters",
    )

    assert settings.APP_ENV == "production"


def test_production_rejects_test_deepseek_credentials():
    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="a-unique-production-secret-with-32-characters",
            AI_FEATURES_ENABLED=True,
            DEEPSEEK_API_KEY="test-only-key",
        )


@pytest.mark.parametrize(
    "production_signal",
    [
        {"DEPLOY_ENABLED": True},
        {"GITHUB_REPO": "snowflake-chan/agora"},
    ],
)
def test_production_signals_reject_test_deepseek_credentials(production_signal):
    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY"):
        Settings(
            _env_file=None,
            APP_ENV="development",
            JWT_SECRET="a-unique-production-secret-with-32-characters",
            AI_FEATURES_ENABLED=True,
            DEEPSEEK_API_KEY="test-only-key",
            **production_signal,
        )


def test_production_accepts_separate_openai_compatible_provider():
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        JWT_SECRET="a-unique-production-secret-with-32-characters",
        AI_FEATURES_ENABLED=True,
        AI_API_KEY="production-only-key",
        AI_BASE_URL="https://provider.example/v1",
        AI_MODEL="production-model",
    )

    assert settings.resolved_ai_api_key() == "production-only-key"
    assert settings.resolved_ai_model() == "production-model"
