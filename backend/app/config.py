from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = ""
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
    AI_MAX_INPUT_CHARS: int = 12000
    AI_RATE_LIMIT_REQUESTS: int = 20
    AI_RATE_LIMIT_IP_REQUESTS: int = 60
    AI_RATE_LIMIT_GLOBAL_REQUESTS: int = 200
    AI_RATE_LIMIT_DAILY_GLOBAL_REQUESTS: int = 2000
    AI_RATE_LIMIT_WINDOW_SECONDS: int = 60
    AI_POLL_RESERVATION_TTL_SECONDS: int = 300

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
        if self.AI_HTTP_TIMEOUT_SECONDS <= 0:
            raise ValueError("AI_HTTP_TIMEOUT_SECONDS must be positive")
        if not 1 <= self.AI_MAX_INPUT_CHARS <= 12000:
            raise ValueError("AI_MAX_INPUT_CHARS must be between 1 and 12000")
        if self.AI_RATE_LIMIT_REQUESTS < 1:
            raise ValueError("AI_RATE_LIMIT_REQUESTS must be positive")
        if self.AI_RATE_LIMIT_IP_REQUESTS < 1:
            raise ValueError("AI_RATE_LIMIT_IP_REQUESTS must be positive")
        if self.AI_RATE_LIMIT_GLOBAL_REQUESTS < 1:
            raise ValueError("AI_RATE_LIMIT_GLOBAL_REQUESTS must be positive")
        if self.AI_RATE_LIMIT_DAILY_GLOBAL_REQUESTS < 1:
            raise ValueError("AI_RATE_LIMIT_DAILY_GLOBAL_REQUESTS must be positive")
        if self.AI_RATE_LIMIT_WINDOW_SECONDS < 1:
            raise ValueError("AI_RATE_LIMIT_WINDOW_SECONDS must be positive")
        if self.AI_POLL_RESERVATION_TTL_SECONDS < 1:
            raise ValueError("AI_POLL_RESERVATION_TTL_SECONDS must be positive")
        if self.AI_FEATURES_ENABLED and production_signals:
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
        return self


settings = Settings()
