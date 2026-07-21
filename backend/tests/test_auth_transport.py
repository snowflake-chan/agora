"""Authentication cookie environment policy tests."""

from app.config import settings
from app.users.backend import cookie_secure


def test_cookie_is_not_secure_for_http_development(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")

    assert cookie_secure() is False


def test_cookie_is_secure_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")

    assert cookie_secure() is True


def test_cookie_is_secure_for_https_public_site(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "PUBLIC_SITE_URL", "https://agora.example")

    assert cookie_secure() is True
