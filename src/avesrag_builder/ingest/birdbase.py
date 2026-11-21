"""BIRDBASE v2025.1 -> raw_birdbase.

Aba Data, com o cabeçalho na segunda linha (a primeira só agrupa colunas).
O id é a coluna "IOC 15.1", a sequência da espécie no BIRDBASE.

Algumas células numéricas estão formatadas como data no Excel (ex.: o 0 e o 1
das colunas Social_* de Antrostomus vociferus aparecem como 00:00 e
1900-01-01). Elas voltam ao número serial do Excel, que é o valor digitado.
"""

import datetime as dt
from pathlib import Path

import pandas as pd
from openpyxl.utils.datetime import to_excel
from pymongo.database import Database

from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import RAW_BIRDBASE
from avesrag_builder.ingest.base import (
    Registro,
    ResultadoIngestao,
    gravar_envelopes,
    registros_de_dataframe,
)

FONTE = "birdbase"
ABA = "Data"
COLUNA_ID = "IOC 15.1"


def desfazer_datas(valor):
    """datetime/time lido de uma célula numérica -> número serial do Excel."""
    if isinstance(valor, (dt.datetime, dt.time)):
        serial = to_excel(valor)
        return int(serial) if float(serial).is_integer() else float(serial)
    return valor


def ler(path: Path) -> list[Registro]:
    df = pd.read_excel(path, sheet_name=ABA, header=1)
    df = df.astype(object).map(desfazer_datas)
    return list(registros_de_dataframe(df, COLUNA_ID))


def ingerir(db: Database, settings: Settings | None = None) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    return [gravar_envelopes(db[RAW_BIRDBASE], ler(settings.BIRDBASE_XLSX), FONTE, completo=True)]
