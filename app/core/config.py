from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str = "Negotia API"
    api_version: str = "0.1.0"
    debug: bool = False
    aws_region: str = "us-east-1"
    aws_profile: str | None = None


settings = Settings()
