"""Escrita idempotente nas collections raw_*.

Toda ingestão produz pares (id na fonte, dados como vieram) e chama
`gravar_envelopes`. Um documento só é escrito quando é novo ou quando o
`source_hash` dos dados mudou: rodar de novo sem mudança na fonte não grava nada.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

import pandas as pd
from pymongo import ReplaceOne
from pymongo.collection import Collection

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.models import RawEnvelope, compute_source_hash

logger = get_logger(__name__)

LOTE = 500

Registro = tuple[str, dict[str, Any]]


class IdDuplicado(ValueError):
    """A mesma chave aparece duas vezes na fonte: a escolha do id está errada."""


@dataclass
class ResultadoIngestao:
    fonte: str
    collection: str
    inseridos: int = 0
    atualizados: int = 0
    inalterados: int = 0
    ausentes_na_fonte: int | None = None  # ids na collection que a fonte não trouxe
    erros: list[str] = field(default_factory=list)

    @property
    def lidos(self) -> int:
        return self.inseridos + self.atualizados + self.inalterados

    @property
    def gravados(self) -> int:
        return self.inseridos + self.atualizados

    def somar(self, outro: ResultadoIngestao) -> None:
        self.inseridos += outro.inseridos
        self.atualizados += outro.atualizados
        self.inalterados += outro.inalterados
        self.erros.extend(outro.erros)

    def resumo(self) -> str:
        partes = [
            f"{self.fonte} -> {self.collection}: {self.lidos} lidos",
            f"{self.inseridos} inseridos",
            f"{self.atualizados} atualizados",
            f"{self.inalterados} inalterados",
        ]
        if self.ausentes_na_fonte:
            partes.append(f"{self.ausentes_na_fonte} na collection mas fora da fonte")
        if self.erros:
            partes.append(f"{len(self.erros)} erros")
        return ", ".join(partes)


# ---------------------------------------------------------------------------
# Conversão de valores para BSON
# ---------------------------------------------------------------------------


def para_bson(valor: Any) -> Any:
    """Converte tipos do pandas/numpy para tipos que o BSON aceita.

    NaN, NaT e pd.NA viram None; inteiros, floats e booleanos do numpy viram os
    nativos do Python; datas viram datetime e horários viram "HH:MM:SS". Dicionários e listas são
    convertidos recursivamente. Strings ficam como vieram.
    """
    if valor is None or valor is pd.NA or valor is pd.NaT:
        return None
    if isinstance(valor, dict):
        return {str(k): para_bson(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [para_bson(v) for v in valor]
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return datetime(valor.year, valor.month, valor.day)
    if isinstance(valor, time):
        return valor.isoformat()
    if hasattr(valor, "item") and not isinstance(valor, (str, bytes)):  # escalares numpy
        valor = valor.item()
    if isinstance(valor, float) and math.isnan(valor):
        return None
    return valor


def id_texto(valor: Any) -> str:
    """Chave da fonte como texto: 3170206.0 -> '3170206', ' CBRO#0004 ' -> 'CBRO#0004'."""
    valor = para_bson(valor)
    if valor is None:
        raise ValueError("id vazio")
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = str(valor).strip()
    if not texto:
        raise ValueError("id vazio")
    return texto


def registros_de_dataframe(
    df: pd.DataFrame, coluna_id: str, prefixo: str = ""
) -> Iterator[Registro]:
    """Uma linha da planilha -> (prefixo + id, linha com as colunas originais)."""
    for linha in df.to_dict("records"):
        dados = {str(k): para_bson(v) for k, v in linha.items()}
        yield f"{prefixo}{id_texto(linha[coluna_id])}", dados


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------


def _checar_duplicados(registros: list[Registro]) -> None:
    vistos: set[str] = set()
    duplicados: list[str] = []
    for id_, _ in registros:
        if id_ in vistos:
            duplicados.append(id_)
        vistos.add(id_)
    if duplicados:
        exemplos = ", ".join(sorted(set(duplicados))[:5])
        raise IdDuplicado(f"{len(duplicados)} ids repetidos na fonte (ex.: {exemplos})")


def gravar_envelopes(
    col: Collection,
    registros: Iterable[Registro],
    fonte: str,
    *,
    completo: bool = False,
    prefixo_completo: str = "",
    agora: datetime | None = None,
) -> ResultadoIngestao:
    """Grava os registros no envelope raw_*, pulando os que não mudaram.

    Com `completo=True`, conta os documentos da collection (com `_id` começando
    por `prefixo_completo`) que a fonte não trouxe desta vez. Eles não são
    apagados: o número vai para o resumo.
    """
    registros = list(registros)
    _checar_duplicados(registros)
    resultado = ResultadoIngestao(fonte=fonte, collection=col.name)

    for inicio in range(0, len(registros), LOTE):
        lote = registros[inicio : inicio + LOTE]
        ids = [id_ for id_, _ in lote]
        existentes = {
            d["_id"]: d.get("source_hash")
            for d in col.find({"_id": {"$in": ids}}, {"source_hash": 1})
        }
        ops = []
        for id_, dados in lote:
            hash_novo = compute_source_hash(dados)
            if existentes.get(id_) == hash_novo:
                resultado.inalterados += 1
                continue
            envelope = RawEnvelope.build(id_, dados, agora=agora)
            ops.append(ReplaceOne({"_id": id_}, envelope.to_mongo(), upsert=True))
            if id_ in existentes:
                resultado.atualizados += 1
            else:
                resultado.inseridos += 1
        if ops:
            col.bulk_write(ops, ordered=False)

    if completo:
        filtro = {"_id": {"$regex": f"^{re.escape(prefixo_completo)}"}} if prefixo_completo else {}
        ids_fonte = {id_ for id_, _ in registros}
        resultado.ausentes_na_fonte = sum(
            1 for d in col.find(filtro, {"_id": 1}) if d["_id"] not in ids_fonte
        )

    logger.info(resultado.resumo())
    return resultado
