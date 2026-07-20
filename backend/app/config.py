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

    model_config = SettingsConfigDict(
        env_file="../.env"
    )

    @model_validator(mode="after")
    def validate_runtime_security(self):
        production_mode = self.APP_ENV.lower() in {"production", "prod"}
        production_signals = production_mode or self.DEPLOY_ENABLED or bool(self.GITHUB_REPO)
        if production_signals and (
            len(self.JWT_SECRET) < 32
            or self.JWT_SECRET in {"change-me-in-production", "test-secret"}
        ):
            raise ValueError(
                "JWT_SECRET must be a unique secret of at least 32 characters in production"
            )
        if self.GOVERNANCE_POLL_SECONDS <= 0:
            raise ValueError("GOVERNANCE_POLL_SECONDS must be positive")
        return self


settings = Settings()
