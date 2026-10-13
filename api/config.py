"""
PostVisit AI - Configuration Settings
Manages environment variables, upload limits, and API metadata.
"""

import os
from pathlib import Path
from typing import Set
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    """Centralized configuration settings for PostVisit AI."""

    PROJECT_NAME: str = "PostVisit AI"
    DESCRIPTION: str = "Clinical consultation processing API"
    VERSION: str = os.getenv("API_VERSION", "1.0.0")

    # Upload and processing constraints
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
    ALLOWED_EXTENSIONS: Set[str] = {
        ".wav",
        ".mp3",
        ".mp4",
        ".m4a",
        ".flac",
        ".ogg",
        ".webm",
        ".aac"
    }

    # LLM configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "") or os.getenv("LLM_API_KEY", "")

    # Supabase persistence configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "postvisit-media")

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_supabase_configured(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_ROLE_KEY)



_settings: Settings = Settings()


def get_settings() -> Settings:
    """Returns singleton settings instance."""
    return _settings
