import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "RecruiterPulse"
    VERSION: str = "1.1.0"
    API_V1_STR: str = "/api/v1"

    # Database
    # Default to fixed local SQLite inside backend folder for instant dev/testing, override with PostgreSQL in production:
    # e.g., postgresql+psycopg://user:password@localhost:5432/recruiterpulse
    DATABASE_URL: str = f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '../../recruiterpulse.db')).replace('\\', '/')}"

    # Security & Auth
    SECRET_KEY: str = "recruiterpulse-super-secret-key-change-in-production-2026"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Google Service Account
    GOOGLE_SERVICE_ACCOUNT_EMAIL: Optional[str] = "sync@recruiterpulse.iam.gserviceaccount.com"
    GOOGLE_SERVICE_ACCOUNT_KEY_PATH: Optional[str] = None

    # Timezone
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

