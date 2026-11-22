"""Configuração do builder, lida do ambiente e do arquivo `.env` na raiz.

Nada é lido no import: use `get_settings()`. As chaves de API são opcionais no
carregamento e cobradas por `Settings.require()` no comando que as usa, para
que `--help` e os testes funcionem sem `.env`.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT_DIR / "data" / "raw"


class MissingSettingError(RuntimeError):
    """Uma variável obrigatória para o comando não está definida."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Chaves de API (obrigatórias por comando)
    OPENAI_API_KEY: SecretStr | None = None
    EBIRD_API_KEY: SecretStr | None = None

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017/?directConnection=true"
    MONGODB_DATABASE: str = "avesrag"

    # LLM e embeddings
    LLM_PROVIDER: Literal["openai"] = "openai"
    LLM_MODEL: str = "gpt-6-luna"
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    # US$ por milhão de tokens na API de batch (a chamada síncrona custa o dobro).
    # Só para a estimativa de custo no resumo do `extract`.
    LLM_PRECO_ENTRADA: float = 0.05
    LLM_PRECO_SAIDA: float = 0.25
    # US$ por milhão de tokens do EMBEDDING_MODEL (chamada síncrona); só para o resumo do `docs`.
    EMBEDDING_PRECO: float = 0.13

    # Piloto e coleta
    PILOTO_MUNICIPIO_IBGE: str = "3170206"
    WIKIAVES_MAX_ESPECIES: int = 0  # 0 = sem limite

    # Caminhos
    CONFIG_DIR: Path = ROOT_DIR / "config"
    REPORTS_DIR: Path = ROOT_DIR / "reports"
    AVONET_XLSX: Path = RAW_DIR / "AVONET Supplementary dataset 1.xlsx"
    BIRDBASE_XLSX: Path = RAW_DIR / "BIRDBASEv2025.1.xlsx"
    CBRO_XLSX: Path = RAW_DIR / "2021.07.26 CBRO 2021 Zenodo Release.xlsx"
    IBGE_XLSX: Path = RAW_DIR / "Bioma_Predominante_por_Municipio_2024.xlsx"
    WIKIAVES_CSV: Path = RAW_DIR / "wikiaves_especies.csv"

    def require(self, *names: str) -> None:
        """Levanta MissingSettingError se alguma das variáveis estiver vazia."""
        faltando = []
        for name in names:
            value = getattr(self, name)
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            if not value:
                faltando.append(name)
        if faltando:
            raise MissingSettingError(
                f"Defina {', '.join(faltando)} no ambiente ou no .env (veja .env.example)."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
