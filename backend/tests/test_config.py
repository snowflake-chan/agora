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
        AI_POLITICAL_CLASSIFIER_URL="http://politics-classifier:8080/classify",
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
            AI_POLITICAL_CLASSIFIER_URL="http://politics-classifier:8080/classify",
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
            AI_POLITICAL_CLASSIFIER_URL="http://politics-classifier:8080/classify",
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
        AI_POLITICAL_CLASSIFIER_URL="http://politics-classifier:8080/classify",
    )

    assert settings.resolved_ai_api_key() == "production-only-key"
    assert settings.resolved_ai_model() == "production-model"


def test_production_content_moderation_requires_at_least_one_semantic_path():
    with pytest.raises(ValidationError, match="production content moderation"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="a-unique-production-secret-with-32-characters",
            AI_POLITICAL_CLASSIFIER_URL="",
        )


def test_production_accepts_explicit_provider_moderation_fallback():
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        JWT_SECRET="a-unique-production-secret-with-32-characters",
        AI_FEATURES_ENABLED=False,
        AI_API_KEY="production-only-key",
        AI_BASE_URL="https://provider.example/v1",
        AI_MODEL="production-model",
        AI_POLITICAL_CLASSIFIER_URL="",
        AI_MODERATION_PROVIDER_FALLBACK_ENABLED=True,
    )

    assert settings.moderation_provider_fallback_is_configured() is True


def test_production_rejects_provider_fallback_without_explicit_opt_in():
    with pytest.raises(ValidationError, match="production content moderation"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="a-unique-production-secret-with-32-characters",
            AI_FEATURES_ENABLED=True,
            AI_API_KEY="production-only-key",
            AI_BASE_URL="https://provider.example/v1",
            AI_MODEL="production-model",
            AI_POLITICAL_CLASSIFIER_URL="",
            AI_MODERATION_PROVIDER_FALLBACK_ENABLED=False,
        )


def test_production_rejects_invalid_classifier_url():
    with pytest.raises(ValidationError, match=r"HTTP\(S\)"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="a-unique-production-secret-with-32-characters",
            AI_POLITICAL_CLASSIFIER_URL="politics-classifier:8080/classify",
        )
