"""Etapa 6 (`docs`): species (só aptas) + b03 -> species_retrieval_docs.

1. Escopo: espécies do piloto ou do registry; delas, só as fichas `apta` geram
   documentos (um por domínio do `b03` com texto).
2. Compara com os documentos gravados dessas espécies (`docs/montar.py`):
   texto e modelo iguais reaproveitam o embedding.
3. Gera os embeddings que faltam, em lotes, por chamada síncrona.
4. Grava só o que mudou e apaga os documentos de espécies do escopo que não
   são mais aptas (ou de domínios que ficaram sem texto), para a busca do chat
   nunca devolver uma espécie que não passou na data quality.

O embedder só é criado (e a chave de API só é cobrada) se houver o que gerar.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError
from pymongo import DeleteOne, ReplaceOne
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.models import EMBEDDING_DIM, RetrievalDoc
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import SPECIES, SPECIES_EXTRACTIONS, SPECIES_RETRIEVAL_DOCS
from avesrag_builder.docs.montar import DocEsperado, Plano, esperados, planejar
from avesrag_builder.fuse.regras import B03
from avesrag_builder.fuse.species import escopo
from avesrag_builder.llm.base import Embedder, ErroFornecedor

log = get_logger(__name__)

LOTE_EMBEDDING = 100
LOTE_MONGO = 200  # cada documento tem 3.072 floats (~30 KB)


@dataclass
class ResultadoDocs:
    escopo: int = 0
    aptas: int = 0
    por_dominio: Counter[str] = field(default_factory=Counter)
    status: Counter[str] = field(default_factory=Counter)
    embeddings: int = 0
    tokens: int = 0
    custo: float = 0.0
    relatorio: Path | None = None

    def linhas(self) -> list[str]:
        dominios = ", ".join(f"{d} {q}" for d, q in sorted(self.por_dominio.items()))
        st = self.status
        return [
            f"docs: {self.aptas} espécies aptas de {self.escopo} no escopo; "
            f"{sum(self.por_dominio.values())} documentos ({dominios or 'nenhum'})",
            f"  novos {st['novo']}, alterados {st['alterado']}, só filtros {st['so_filtros']}, "
            f"inalterados {st['inalterado']}, removidos {st['removido']}",
            f"  embeddings: {self.embeddings} ({self.tokens} tokens, "
            f"custo estimado US$ {self.custo:.4f})",
            *([f"  relatório: {self.relatorio}"] if self.relatorio else []),
        ]


def _gerar_embeddings(
    docs: list[DocEsperado], embedder: Embedder, modelo: str, res: ResultadoDocs
) -> dict[str, list[float]]:
    vetores: dict[str, list[float]] = {}
    for i in range(0, len(docs), LOTE_EMBEDDING):
        lote = docs[i : i + LOTE_EMBEDDING]
        resposta = embedder.embeddings([d.texto for d in lote], modelo)
        if len(resposta.vetores) != len(lote):
            raise ErroFornecedor(
                f"embeddings: {len(resposta.vetores)} vetores para {len(lote)} textos"
            )
        for doc, vetor in zip(lote, resposta.vetores, strict=True):
            if len(vetor) != EMBEDDING_DIM:
                raise ErroFornecedor(
                    f"embedding de {doc.id} com {len(vetor)} posições; esperado {EMBEDDING_DIM}"
                )
            vetores[doc.id] = vetor
        res.tokens += resposta.tokens
        res.embeddings += len(lote)
        log.info(f"embeddings: {res.embeddings} de {len(docs)}")
    return vetores


def _documento(doc: DocEsperado, vetor: list[float], modelo: str, agora: datetime) -> RetrievalDoc:
    return RetrievalDoc(
        id=doc.id,
        species_id=doc.species_id,
        dominio=doc.dominio,
        texto=doc.texto,
        nomes=doc.nomes,
        embedding=vetor,
        modelo=modelo,
        filtros=doc.filtros,
        built_at=agora,
    )


def _relatorio(caminho: Path, plano: Plano, textos: dict[str, str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["species_id", "dominio", "status", "caracteres"])
        for _id in sorted(plano.status):
            sid, dominio = _id.rsplit(":", 1)
            w.writerow([sid, dominio, plano.status[_id], len(textos.get(_id, ""))])


def executar(
    db: Database,
    obter_embedder: Callable[[], Embedder],
    piloto: bool = False,
    settings: Settings | None = None,
) -> ResultadoDocs:
    settings = settings or get_settings()
    modelo = settings.EMBEDDING_MODEL

    ids = escopo(db, piloto)
    if not ids:
        raise ValueError("nenhuma espécie no escopo: rode `resolve` antes")
    res = ResultadoDocs(escopo=len(ids))

    fichas = list(db[SPECIES].find({"species_id": {"$in": ids}, "_meta.dq_status": "apta"}))
    res.aptas = len(fichas)
    b03 = {
        d["species_id"]: d
        for d in db[SPECIES_EXTRACTIONS].find(
            {"species_id": {"$in": [f["species_id"] for f in fichas]}, "prompt": B03}
        )
    }
    docs = [doc for f in fichas for doc in esperados(f, b03.get(f["species_id"]))]
    res.por_dominio.update(d.dominio for d in docs)

    col = db[SPECIES_RETRIEVAL_DOCS]
    existentes = {
        d["_id"]: d
        for d in col.find(
            {"species_id": {"$in": ids}}, {"texto": 1, "modelo": 1, "nomes": 1, "filtros": 1}
        )
    }
    plano = planejar(docs, existentes, modelo)
    res.status.update(plano.status.values())

    vetores = _gerar_embeddings(plano.gerar, obter_embedder(), modelo, res) if plano.gerar else {}
    res.custo = res.tokens / 1e6 * settings.EMBEDDING_PRECO
    if plano.reaproveitar:
        ids_reuso = [d.id for d in plano.reaproveitar]
        for d in col.find({"_id": {"$in": ids_reuso}}, {"embedding": 1}):
            vetores[d["_id"]] = d["embedding"]

    agora = datetime.now(UTC)
    ops: list[ReplaceOne | DeleteOne] = []
    try:
        for doc in [*plano.gerar, *plano.reaproveitar]:
            novo = _documento(doc, vetores[doc.id], modelo, agora).to_mongo()
            ops.append(ReplaceOne({"_id": doc.id}, novo, upsert=True))
    except ValidationError as e:
        raise ValueError(f"documento de busca inválido: {e}") from e
    ops += [DeleteOne({"_id": _id}) for _id in plano.remover]
    for i in range(0, len(ops), LOTE_MONGO):
        col.bulk_write(ops[i : i + LOTE_MONGO], ordered=False)

    res.relatorio = settings.REPORTS_DIR / "docs.tsv"
    _relatorio(res.relatorio, plano, {d.id: d.texto for d in docs})
    log.info(
        f"docs: {len(plano.gerar)} com embedding novo, {len(plano.reaproveitar)} só filtros, "
        f"{len(plano.remover)} removidos"
    )
    return res
