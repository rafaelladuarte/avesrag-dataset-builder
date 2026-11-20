from pathlib import Path
from typing import Optional

from pydantic import MongoDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # MongoDB
    MONGODB_URI: MongoDsn
    MONGODB_DATABASE: str = "avesrag"

    # Ingestion / APIs
    EBIRD_API_KEY: Optional[str] = None
    MAX_ESPECIES: int = 0
    AVONET_CSV: str = "data/raw/AVONET Supplementary dataset 1.xlsx"

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
