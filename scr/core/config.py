from pathlib import Path
from typing import Optional

from pydantic import MongoDsn, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # MongoDB
    MONGODB_URI: MongoDsn
    MONGODB_DATABASE: str = "avesrag"

    # PostgreSQL (Opcional por enquanto)
    POSTGRES_URI: Optional[PostgresDsn] = None

    # Ingestion / APIs
    GEMINI_API_KEY: str
    EBIRD_API_KEY: Optional[str] = None
    MAX_ESPECIES: int = 0
    AVONET_CSV: str = "data/AVONET_BirdLife.xlsx"

    # Gemini Rate Limiting
    GEMINI_RPM: int = 10  # Requests per minute
    GEMINI_TPM: int = 250000  # Tokens per minute
    GEMINI_RPD: int = 500  # Requests per day

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
