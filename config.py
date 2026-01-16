from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # API
    app_name: str = "AdFlow AI"
    debug: bool = False

    # Claude API
    anthropic_api_key: str = ""
    claude_model_main: str = "claude-sonnet-4-20250514"
    claude_model_fast: str = "claude-haiku-4-20250514"

    # Database
    database_url: str = "sqlite+aiosqlite:///./adflow.db"

    # nano-banana (placeholder)
    nano_banana_api_key: str = ""
    nano_banana_api_url: str = "https://api.nano-banana.com/v1"

    # Limits
    max_creatives_per_project: int = 100
    max_retries_per_stage: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
