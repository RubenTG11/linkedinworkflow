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

    # Writer Features (can be toggled to disable new features)
    writer_multi_draft_enabled: bool = True  # Generate multiple drafts and select best
    writer_multi_draft_count: int = 3  # Number of drafts to generate (2-5)
    writer_semantic_matching_enabled: bool = True  # Use semantically similar example posts
    writer_learn_from_feedback: bool = True  # Learn from recurring critic feedback
    writer_feedback_history_count: int = 10  # Number of past posts to analyze for patterns

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()
