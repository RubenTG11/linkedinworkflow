"""Configuration management for LinkedIn Workflow."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    openai_api_key: str
    perplexity_api_key: str
    apify_api_key: str

    # Supabase
    supabase_url: str
    supabase_key: str

    # Apify
    apify_actor_id: str = "apimaestro~linkedin-profile-posts"

    # Web Interface
    web_password: str = ""
    session_secret: str = ""

    # Development
    debug: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()
