"""IBGE, bioma predominante por município -> raw_ibge.

Aba Lista_Predominante, com o título na primeira linha e o cabeçalho na segunda.
O id é o geocódigo do município (ex.: "3170206", Uberlândia).
"""

from pathlib import Path

import pandas as pd
from pymongo.database import Database

from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import RAW_IBGE
from avesrag_builder.ingest.base import (
    Registro,
    ResultadoIngestao,
    gravar_envelopes,
    registros_de_dataframe,
)

FONTE = "ibge"
ABA = "Lista_Predominante"
COLUNA_ID = "Geocódigo"


def ler(path: Path) -> list[Registro]:
    df = pd.read_excel(path, sheet_name=ABA, header=1)
    return list(registros_de_dataframe(df, COLUNA_ID))


def ingerir(db: Database, settings: Settings | None = None) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    return [gravar_envelopes(db[RAW_IBGE], ler(settings.IBGE_XLSX), FONTE, completo=True)]
