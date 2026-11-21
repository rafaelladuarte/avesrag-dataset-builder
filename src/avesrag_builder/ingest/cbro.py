"""CBRO 2021 -> raw_cbro.

Grava só as linhas de categoria "Espécie" da Lista Primária (1.971), com o
`#CBRO` como id. Ordens, famílias, gêneros e subespécies ficam de fora.
"""

from pathlib import Path

import pandas as pd
from pymongo.database import Database

from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import RAW_CBRO
from avesrag_builder.ingest.base import (
    Registro,
    ResultadoIngestao,
    gravar_envelopes,
    registros_de_dataframe,
)

FONTE = "cbro"
ABA = "Lista Primária"
CATEGORIA_ESPECIE = "Espécie"


def ler(path: Path) -> list[Registro]:
    df = pd.read_excel(path, sheet_name=ABA)
    especies = df[df["Categoria"] == CATEGORIA_ESPECIE]
    return list(registros_de_dataframe(especies, "#CBRO"))


def ingerir(db: Database, settings: Settings | None = None) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    return [gravar_envelopes(db[RAW_CBRO], ler(settings.CBRO_XLSX), FONTE, completo=True)]
