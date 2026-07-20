from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    JWT_SECRET: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""
    SUPER_ADMIN_EMAIL: str = ""
    CORS_ORIGIN: str = ""
    DEPLOY_ENABLED: bool = True
    REPO_DIR: str = "/repo"
    REDIS_URL: str = "redis://redis:6379/0"
    AUTH_LOGIN_ATTEMPTS: int = 10
    AUTH_LOGIN_WINDOW_SECONDS: int = 300
    AUTH_REGISTER_ATTEMPTS: int = 30
    AUTH_REGISTER_WINDOW_SECONDS: int = 3600

    model_config = SettingsConfigDict(
        env_file="../.env"
    )


settings = Settings()
