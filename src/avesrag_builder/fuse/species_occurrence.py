"""raw_ebird + raw_ibge -> species_occurrence (parte da etapa 4, `fuse`).

Para cada município de `raw_ebird` (`municipio:<geocódigo>`, com a lista de
`speciesCode`), junta o nome, a UF e o bioma predominante do `raw_ibge` e agrupa
por espécie. O `speciesCode` vira `species_id` pelo `chaves.ebird` do registry;
um código sem espécie no registry é só contado.

Determinístico: municípios ordenados por geocódigo e biomas em ordem alfabética.
Grava só o que mudou (o `atualizado_em` não entra na comparação) e não apaga as
espécies que deixaram de ter registro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pymongo import InsertOne, ReplaceOne
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.models import Municipio, SpeciesOccurrence
from avesrag_builder.db.collections import (
    RAW_EBIRD,
    RAW_IBGE,
    SPECIES_OCCURRENCE,
    SPECIES_REGISTRY,
    garantir_indices,
)
from avesrag_builder.ingest.base import ResultadoIngestao

log = get_logger(__name__)

PREFIXO_MUNICIPIO = "municipio:"
LOTE = 500


@dataclass
class Ocorrencias:
    por_especie: dict[str, SpeciesOccurrence] = field(default_factory=dict)
    codigos_sem_especie: set[str] = field(default_factory=set)
    municipios: int = 0


def _municipio(dados_ebird: dict[str, Any], ibge: dict[str, Any] | None) -> Municipio:
    geocodigo = str(dados_ebird.get("geocodigo"))
    ibge = ibge or {}
    return Municipio(
        geocodigo=geocodigo,
        nome=ibge.get("Nome do município") or dados_ebird.get("nome"),
        uf=ibge.get("Sigla da UF") or dados_ebird.get("uf"),
        bioma=ibge.get("Bioma predominante"),
    )


def agrupar(
    municipios_ebird: list[dict[str, Any]],
    ibge: dict[str, dict[str, Any]],
    especie_por_codigo: dict[str, str],
    agora: datetime | None = None,
) -> Ocorrencias:
    """Função pura: `dados` dos municípios do eBird, IBGE por geocódigo e speciesCode -> species_id."""
    agora = agora or datetime.now(UTC)
    res = Ocorrencias(municipios=len(municipios_ebird))
    acumulado: dict[str, dict[str, Municipio]] = {}
    for dados in municipios_ebird:
        mun = _municipio(dados, ibge.get(str(dados.get("geocodigo"))))
        for codigo in dados.get("especies") or []:
            sid = especie_por_codigo.get(codigo)
            if sid is None:
                res.codigos_sem_especie.add(codigo)
                continue
            acumulado.setdefault(sid, {})[mun.geocodigo] = mun
    for sid in sorted(acumulado):
        muns = [acumulado[sid][g] for g in sorted(acumulado[sid])]
        res.por_especie[sid] = SpeciesOccurrence(
            species_id=sid,
            municipios=muns,
            biomas=sorted({m.bioma for m in muns if m.bioma}),
            n_municipios=len(muns),
            atualizado_em=agora,
        )
    return res


def calcular(db: Database) -> Ocorrencias:
    municipios = [
        d["dados"] for d in db[RAW_EBIRD].find({"_id": {"$regex": f"^{PREFIXO_MUNICIPIO}"}})
    ]
    geocodigos = [str(m.get("geocodigo")) for m in municipios]
    ibge = {d["_id"]: d["dados"] for d in db[RAW_IBGE].find({"_id": {"$in": geocodigos}})}
    especie_por_codigo = {
        d["chaves"]["ebird"]: d["species_id"]
        for d in db[SPECIES_REGISTRY].find(
            {"chaves.ebird": {"$ne": None}}, {"species_id": 1, "chaves.ebird": 1}
        )
    }
    return agrupar(municipios, ibge, especie_por_codigo)


def _sem_data(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in doc.items() if k not in ("_id", "atualizado_em")}


def gravar(db: Database, ocorrencias: Ocorrencias) -> ResultadoIngestao:
    garantir_indices(db)
    col = db[SPECIES_OCCURRENCE]
    resultado = ResultadoIngestao(fonte="fuse", collection=SPECIES_OCCURRENCE)
    existentes = {d["species_id"]: d for d in col.find({})}
    ops: list[InsertOne | ReplaceOne] = []
    for sid, occ in ocorrencias.por_especie.items():
        doc = occ.to_mongo()
        atual = existentes.get(sid)
        if atual is None:
            ops.append(InsertOne(doc))
            resultado.inseridos += 1
        elif _sem_data(atual) == _sem_data(doc):
            resultado.inalterados += 1
        else:
            ops.append(ReplaceOne({"species_id": sid}, doc))
            resultado.atualizados += 1
    for i in range(0, len(ops), LOTE):
        col.bulk_write(ops[i : i + LOTE], ordered=False)
    resultado.ausentes_na_fonte = sum(1 for sid in existentes if sid not in ocorrencias.por_especie)
    return resultado


def executar(db: Database) -> tuple[Ocorrencias, ResultadoIngestao]:
    ocorrencias = calcular(db)
    resultado = gravar(db, ocorrencias)
    log.info(resultado.resumo())
    return ocorrencias, resultado
