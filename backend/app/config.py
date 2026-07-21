from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    PUBLIC_SITE_URL: str = ""
    DB_ECHO: bool = False
    JWT_SECRET: str = ""
    APP_ENV: str = "production"
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""
    SUPER_ADMIN_EMAIL: str = ""
    CORS_ORIGIN: str = ""
    DEPLOY_ENABLED: bool = False
    GOVERNANCE_POLL_SECONDS: float = 60.0
    REPO_DIR: str = "/repo"
    REDIS_URL: str = "redis://redis:6379/0"
    AUTH_LOGIN_ATTEMPTS: int = 10
    AUTH_LOGIN_WINDOW_SECONDS: int = 300
    AUTH_REGISTER_ATTEMPTS: int = 30
    AUTH_REGISTER_WINDOW_SECONDS: int = 3600
    AUTH_SESSION_MAX_AGE_SECONDS: int = 2592000
    AUTH_MAX_SESSIONS_PER_USER: int = 3
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    # Test and development only. Production uses the provider-neutral fields
    # below so a test key cannot be carried forward by accident.
    AI_API_KEY: str = ""
    AI_BASE_URL: str = ""
    AI_MODEL: str = ""
    AI_FEATURES_ENABLED: bool = False
    AI_HTTP_TIMEOUT_SECONDS: float = 20.0
    AI_TEMPERATURE: float = 0.0
    AI_RESPONSE_FORMAT_ENABLED: bool = True
    # Provider-specific reasoning controls are opt-in. An empty value keeps the
    # OpenAI-compatible request portable across providers.
    AI_THINKING_MODE: str = ""
    # Trusted in-network semantic gate, required before production AI egress.
    AI_POLITICAL_CLASSIFIER_URL: str = ""
    AI_POLITICAL_CLASSIFIER_TIMEOUT_SECONDS: float = 3.0
    # A provider fallback is an explicit operational choice. The in-network
    # classifier remains preferred whenever both paths are configured.
    AI_MODERATION_PROVIDER_FALLBACK_ENABLED: bool = False
    AI_MODERATION_POLICY_VERSION: str = "semantic-politics-v1"
    AI_POLITICAL_CLASSIFIER_VERSION: str = "semantic-classifier-v1"
    AI_MODERATION_CACHE_TTL_SECONDS: int = 604800
    AI_MODERATION_RATE_LIMIT_GLOBAL_QPS: int = 12
    AI_MODERATION_RATE_LIMIT_DAILY_GLOBAL_REQUESTS: int = 10000
    AI_MODERATION_MAX_CONCURRENT_REQUESTS: int = 8
    AI_MAX_INPUT_CHARS: int = 12000
    AI_RATE_LIMIT_REQUESTS: int = 20
    AI_RATE_LIMIT_IP_REQUESTS: int = 60
    AI_RATE_LIMIT_GLOBAL_REQUESTS: int = 200
    AI_RATE_LIMIT_GLOBAL_QPS: int = 8
    AI_RATE_LIMIT_DAILY_GLOBAL_REQUESTS: int = 2000
    AI_RATE_LIMIT_WINDOW_SECONDS: int = 60
    AI_POLL_RESERVATION_TTL_SECONDS: int = 300
    AI_TRANSLATION_CACHE_TTL_SECONDS: int = 604800
    DAILY_QUESTION_ENABLED: bool = True
    DAILY_QUESTION_HOUR_UTC: int = 9
    AI_MAX_CONCURRENT_REQUESTS: int = 8

    model_config = SettingsConfigDict(
        env_file="../.env"
    )

    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"production", "prod"}

    def uses_production_ai_provider(self) -> bool:
        return self.is_production() or self.DEPLOY_ENABLED or bool(self.GITHUB_REPO)

    def resolved_ai_api_key(self) -> str:
        return (
            self.AI_API_KEY
            if self.uses_production_ai_provider()
            else self.DEEPSEEK_API_KEY
        )

    def resolved_ai_base_url(self) -> str:
        return (
            self.AI_BASE_URL
            if self.uses_production_ai_provider()
            else self.DEEPSEEK_BASE_URL
        )

    def resolved_ai_model(self) -> str:
        return (
            self.AI_MODEL
            if self.uses_production_ai_provider()
            else self.DEEPSEEK_MODEL
        )

    def ai_provider_is_configured(self) -> bool:
        return bool(
            self.resolved_ai_api_key().strip()
            and self.resolved_ai_base_url().strip()
            and self.resolved_ai_model().strip()
        )

    def moderation_provider_fallback_is_configured(self) -> bool:
        return bool(
            self.AI_MODERATION_PROVIDER_FALLBACK_ENABLED
            and self.ai_provider_is_configured()
        )

    @model_validator(mode="after")
    def validate_runtime_security(self):
        production_signals = self.uses_production_ai_provider()
        if production_signals and (
            len(self.JWT_SECRET) < 32
            or self.JWT_SECRET in {"change-me-in-production", "test-secret"}
        ):
            raise ValueError(
                "JWT_SECRET must be a unique secret of at least 32 characters in production"
            )
        if self.GOVERNANCE_POLL_SECONDS <= 0:
            raise ValueError("GOVERNANCE_POLL_SECONDS must be positive")
        if self.AUTH_SESSION_MAX_AGE_SECONDS < 1:
            raise ValueError("AUTH_SESSION_MAX_AGE_SECONDS must be positive")
        if self.AUTH_MAX_SESSIONS_PER_USER < 1:
            raise ValueError("AUTH_MAX_SESSIONS_PER_USER must be positive")
        if self.AI_HTTP_TIMEOUT_SECONDS <= 0:
            raise ValueError("AI_HTTP_TIMEOUT_SECONDS must be positive")
        if not 0 <= self.AI_TEMPERATURE <= 2:
            raise ValueError("AI_TEMPERATURE must be between 0 and 2")
        if self.AI_THINKING_MODE not in {"", "disabled", "enabled"}:
            raise ValueError(
                "AI_THINKING_MODE must be empty, disabled, or enabled"
            )
        if self.AI_POLITICAL_CLASSIFIER_TIMEOUT_SECONDS <= 0:
            raise ValueError("AI_POLITICAL_CLASSIFIER_TIMEOUT_SECONDS must be positive")
        if not self.AI_MODERATION_POLICY_VERSION.strip():
            raise ValueError("AI_MODERATION_POLICY_VERSION must not be empty")
        if not self.AI_POLITICAL_CLASSIFIER_VERSION.strip():
            raise ValueError("AI_POLITICAL_CLASSIFIER_VERSION must not be empty")
        if self.AI_MODERATION_CACHE_TTL_SECONDS < 1:
            raise ValueError("AI_MODERATION_CACHE_TTL_SECONDS must be positive")
        if self.AI_MODERATION_RATE_LIMIT_GLOBAL_QPS < 1:
            raise ValueError("AI_MODERATION_RATE_LIMIT_GLOBAL_QPS must be positive")
        if self.AI_MODERATION_RATE_LIMIT_DAILY_GLOBAL_REQUESTS < 1:
            raise ValueError(
                "AI_MODERATION_RATE_LIMIT_DAILY_GLOBAL_REQUESTS must be positive"
            )
        if self.AI_MODERATION_MAX_CONCURRENT_REQUESTS < 1:
            raise ValueError("AI_MODERATION_MAX_CONCURRENT_REQUESTS must be positive")
        if not 1 <= self.AI_MAX_INPUT_CHARS <= 12000:
            raise ValueError("AI_MAX_INPUT_CHARS must be between 1 and 12000")
        if self.AI_RATE_LIMIT_REQUESTS < 1:
            raise ValueError("AI_RATE_LIMIT_REQUESTS must be positive")
        if self.AI_RATE_LIMIT_IP_REQUESTS < 1:
            raise ValueError("AI_RATE_LIMIT_IP_REQUESTS must be positive")
        if self.AI_RATE_LIMIT_GLOBAL_REQUESTS < 1:
            raise ValueError("AI_RATE_LIMIT_GLOBAL_REQUESTS must be positive")
        if self.AI_RATE_LIMIT_GLOBAL_QPS < 1:
            raise ValueError("AI_RATE_LIMIT_GLOBAL_QPS must be positive")
        if self.AI_RATE_LIMIT_DAILY_GLOBAL_REQUESTS < 1:
            raise ValueError("AI_RATE_LIMIT_DAILY_GLOBAL_REQUESTS must be positive")
        if self.AI_RATE_LIMIT_WINDOW_SECONDS < 1:
            raise ValueError("AI_RATE_LIMIT_WINDOW_SECONDS must be positive")
        if self.AI_POLL_RESERVATION_TTL_SECONDS < 1:
            raise ValueError("AI_POLL_RESERVATION_TTL_SECONDS must be positive")
        if self.AI_TRANSLATION_CACHE_TTL_SECONDS < 1:
            raise ValueError("AI_TRANSLATION_CACHE_TTL_SECONDS must be positive")
        if not 0 <= self.DAILY_QUESTION_HOUR_UTC <= 23:
            raise ValueError("DAILY_QUESTION_HOUR_UTC must be between 0 and 23")
        if self.AI_MAX_CONCURRENT_REQUESTS < 1:
            raise ValueError("AI_MAX_CONCURRENT_REQUESTS must be positive")
        if production_signals:
            local_classifier = self.AI_POLITICAL_CLASSIFIER_URL.strip()
            if local_classifier and not local_classifier.startswith(
                ("http://", "https://")
            ):
                raise ValueError(
                    "AI_POLITICAL_CLASSIFIER_URL must be an HTTP(S) endpoint"
                )
        local_classifier = self.AI_POLITICAL_CLASSIFIER_URL.strip()
        production_provider_required = bool(
            self.AI_FEATURES_ENABLED
            or (
                not local_classifier
                and self.AI_MODERATION_PROVIDER_FALLBACK_ENABLED
            )
        )
        if production_provider_required and production_signals:
            if self.DEEPSEEK_API_KEY:
                raise ValueError(
                    "DEEPSEEK_API_KEY is test/development only; use AI_API_KEY in production"
                )
            if not all(
                (
                    self.AI_API_KEY.strip(),
                    self.AI_BASE_URL.strip(),
                    self.AI_MODEL.strip(),
                )
            ):
                raise ValueError(
                    "AI_API_KEY, AI_BASE_URL, and AI_MODEL are required when production AI is enabled"
                )
            if not self.AI_BASE_URL.startswith("https://"):
                raise ValueError("AI_BASE_URL must use HTTPS in production")
        if production_signals and self.AI_FEATURES_ENABLED and not (
            self.AI_POLITICAL_CLASSIFIER_URL.strip()
            or self.moderation_provider_fallback_is_configured()
        ):
            raise ValueError(
                "production content moderation requires AI_POLITICAL_CLASSIFIER_URL "
                "or an explicitly enabled AI provider fallback"
            )
        return self


settings = Settings()
