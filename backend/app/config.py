from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    JWT_SECRET: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""

    model_config = SettingsConfigDict(
        env_file="../.env"
    )


settings = Settings()