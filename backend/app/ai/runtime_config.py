import asyncio
import base64
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from time import monotonic

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app.config import settings
from app.db import async_session
from app.db.models.settings import SiteSetting


logger = logging.getLogger(__name__)
AI_PROVIDER_SETTING_KEY = "ai_provider_config"
_CACHE_SECONDS = 5.0
_cache_lock = asyncio.Lock()
_cached_config: "AIRuntimeConfig | None" = None
_cache_expires_at = 0.0


@dataclass(frozen=True)
class AIRuntimeConfig:
    enabled: bool
    api_key: str
    base_url: str
    model: str
    moderation_provider_fallback_enabled: bool
    source: str

    def provider_is_configured(self) -> bool:
        return bool(self.api_key.strip() and self.base_url.strip() and self.model.strip())


def environment_ai_config() -> AIRuntimeConfig:
    return AIRuntimeConfig(
        enabled=settings.AI_FEATURES_ENABLED,
        api_key=settings.resolved_ai_api_key().strip(),
        base_url=settings.resolved_ai_base_url().strip(),
        model=settings.resolved_ai_model().strip(),
        moderation_provider_fallback_enabled=(
            settings.AI_MODERATION_PROVIDER_FALLBACK_ENABLED
        ),
        source="environment",
    )


def _fernet() -> Fernet:
    digest = hashlib.sha256(
        f"agora-ai-provider:{settings.JWT_SECRET}".encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_api_key(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")


def serialize_database_config(config: AIRuntimeConfig) -> str:
    payload = asdict(config)
    payload.pop("source", None)
    payload["api_key"] = encrypt_api_key(config.api_key) if config.api_key else ""
    payload["version"] = 1
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def parse_database_config(value: str) -> AIRuntimeConfig | None:
    try:
        payload = json.loads(value)
        if not isinstance(payload, dict) or payload.get("version") != 1:
            return None
        ciphertext = payload.get("api_key", "")
        api_key = decrypt_api_key(ciphertext) if ciphertext else ""
        return AIRuntimeConfig(
            enabled=bool(payload.get("enabled", False)),
            api_key=api_key,
            base_url=str(payload.get("base_url", "")).strip(),
            model=str(payload.get("model", "")).strip(),
            moderation_provider_fallback_enabled=bool(
                payload.get("moderation_provider_fallback_enabled", False)
            ),
            source="database",
        )
    except (InvalidToken, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Stored AI provider configuration is unreadable; using environment fallback")
        return None


async def get_ai_runtime_config(*, force_refresh: bool = False) -> AIRuntimeConfig:
    global _cached_config, _cache_expires_at
    now = monotonic()
    if not force_refresh and _cached_config is not None and now < _cache_expires_at:
        return _cached_config

    async with _cache_lock:
        now = monotonic()
        if not force_refresh and _cached_config is not None and now < _cache_expires_at:
            return _cached_config
        config = environment_ai_config()
        try:
            async with async_session() as session:
                row = (
                    await session.execute(
                        select(SiteSetting).where(
                            SiteSetting.key == AI_PROVIDER_SETTING_KEY
                        )
                    )
                ).scalar_one_or_none()
                if row and row.value:
                    config = parse_database_config(row.value) or config
        except Exception as exc:
            logger.warning(
                "AI provider configuration load failed type=%s; using environment fallback",
                type(exc).__name__,
            )
        _cached_config = config
        _cache_expires_at = monotonic() + _CACHE_SECONDS
        return config


def invalidate_ai_runtime_config() -> None:
    global _cached_config, _cache_expires_at
    _cached_config = None
    _cache_expires_at = 0.0
