"""AVONET -> raw_avonet.

Grava as duas abas de espécies e a tabela de correspondência entre elas:

- `birdlife:<Species1>`: aba AVONET1_BirdLife (taxonomia BirdLife)
- `ebird:<Species2>`: aba AVONET2_eBird (taxonomia eBird/Clements)
- `crosswalk:<Species1>|<Species2>`: aba "BirdLife-eBird crosswalk"
  (um dos lados pode vir vazio quando não há correspondência)
"""

from pathlib import Path

import pandas as pd
from pymongo.database import Database

from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import RAW_AVONET
from avesrag_builder.ingest.base import (
    Registro,
    ResultadoIngestao,
    gravar_envelopes,
    para_bson,
    registros_de_dataframe,
)

FONTE = "avonet"
ABA_BIRDLIFE = "AVONET1_BirdLife"
ABA_EBIRD = "AVONET2_eBird"
ABA_CROSSWALK = "BirdLife-eBird crosswalk"


def _sem_colunas_vazias(df: pd.DataFrame) -> pd.DataFrame:
    """Remove colunas sem cabeçalho (o Excel do AVONET tem algumas à direita)."""
    return df.loc[:, [not str(c).startswith("Unnamed:") for c in df.columns]]


def registros_crosswalk(df: pd.DataFrame) -> list[Registro]:
    registros = []
    for linha in _sem_colunas_vazias(df).to_dict("records"):
        dados = {str(k): para_bson(v) for k, v in linha.items()}
        s1 = dados.get("Species1") or ""
        s2 = dados.get("Species2") or ""
        if not s1 and not s2:
            continue
        registros.append((f"crosswalk:{s1}|{s2}", dados))
    return registros


def ler(path: Path) -> list[Registro]:
    planilha = pd.ExcelFile(path)
    birdlife = _sem_colunas_vazias(planilha.parse(ABA_BIRDLIFE))
    ebird = _sem_colunas_vazias(planilha.parse(ABA_EBIRD))
    crosswalk = planilha.parse(ABA_CROSSWALK)
    return [
        *registros_de_dataframe(birdlife, "Species1", prefixo="birdlife:"),
        *registros_de_dataframe(ebird, "Species2", prefixo="ebird:"),
        *registros_crosswalk(crosswalk),
    ]


def ingerir(db: Database, settings: Settings | None = None) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    registros = ler(settings.AVONET_XLSX)
    return [gravar_envelopes(db[RAW_AVONET], registros, FONTE, completo=True)]
