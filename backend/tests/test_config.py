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
