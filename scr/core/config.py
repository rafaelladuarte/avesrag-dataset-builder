from typing import Optional

from pydantic import MongoDsn, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
