from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    JWT_SECRET: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""
    CORS_ORIGIN: str = ""
    DEPLOY_ENABLED: bool = True
    REPO_DIR: str = "/repo"

    model_config = SettingsConfigDict(
        env_file="../.env"
    )


settings = Settings()