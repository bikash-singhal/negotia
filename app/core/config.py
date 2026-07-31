from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Negotia API"
    api_version: str = "0.1.0"
    debug: bool = False
    database_url: str = "postgresql+psycopg://localhost:5432/negotia"
    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    llm_provider: Literal["fake", "bedrock"] = "fake"
    bedrock_model_id: str = "amazon.nova-lite-v1:0"


settings = Settings()
