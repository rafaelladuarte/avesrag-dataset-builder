"""Bird Album (repositório huashu-bird-sticker) -> raw_birdalbum.

Lê o `data/species.csv` do repositório, num commit fixo (`BIRDALBUM_REF`), com
uma linha por espécie da AviList 2026: nome científico, código do eBird, arquivo
da ilustração e os campos de qualidade (`meets_quality_bar`, `review_score`,
`reference_type`). O id é o da própria fonte (ex.: "Pitangus_sulphuratus").

As ilustrações são geradas por IA e publicadas sob CC BY 4.0; os dados de
`data/` são MIT. A ilustração entra na ficha como mídia secundária (`fuse`).
"""

from __future__ import annotations

import csv
import io

import requests
from pymongo.database import Database

from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import RAW_BIRDALBUM
from avesrag_builder.ingest.base import Registro, ResultadoIngestao, gravar_envelopes

FONTE = "birdalbum"
ARQUIVO = "data/species.csv"
TIMEOUT_S = 120

# Crédito e licença pedidos no LICENSE.md do repositório.
LICENCA = "CC BY 4.0"
LICENCA_FONTE = "CC-BY-4.0"  # como aparece na coluna sticker_license
CREDITO = f"Bird stickers: huashu-bird-sticker by Huashu, {LICENCA}"


def url_raw(repo: str, ref: str, caminho: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{caminho}"


def link_repositorio(repo: str) -> str:
    return f"https://github.com/{repo}"


def ler(texto: str) -> list[Registro]:
    return [(linha["id"], dict(linha)) for linha in csv.DictReader(io.StringIO(texto))]


def baixar(settings: Settings) -> str:
    url = url_raw(settings.BIRDALBUM_REPO, settings.BIRDALBUM_REF, ARQUIVO)
    r = requests.get(url, timeout=TIMEOUT_S)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def ingerir(db: Database, settings: Settings | None = None) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    registros = ler(baixar(settings))
    return [gravar_envelopes(db[RAW_BIRDALBUM], registros, FONTE, completo=True)]
