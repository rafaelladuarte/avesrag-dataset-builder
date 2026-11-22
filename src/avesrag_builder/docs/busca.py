"""Busca de espécies por vetor e consultas de fumaça (`index --fumaca`).

`buscar_especies` é uma referência simples para o retriever do assistant, não o
retriever: um `$vectorSearch` em species_retrieval_docs, com as espécies
ordenadas pela maior nota entre os seus documentos. A soma das notas também é
calculada, só para comparação: as notas do cosseno ficam todas perto de 0,7, e
somar os três domínios soma ruído (plano_marco6.md §12).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pymongo.database import Database

from avesrag_builder.core.models import SpeciesId
from avesrag_builder.core.vocabulario import VocabularioInvalido, _erros_pydantic, _ler_yaml
from avesrag_builder.db.collections import SPECIES_RETRIEVAL_DOCS
from avesrag_builder.docs.indices import INDICE_VETOR
from avesrag_builder.docs.montar import DOMINIOS
from avesrag_builder.llm.base import Embedder

NUM_CANDIDATOS = 200
LIMITE_DOCUMENTOS = 60


@dataclass(frozen=True)
class Candidata:
    species_id: str
    soma: float
    maior: float


def agregar(acertos: Iterable[tuple[str, float]], k: int = 10) -> list[Candidata]:
    """(species_id, nota) de cada documento -> top k espécies pela maior nota."""
    somas: dict[str, float] = {}
    maiores: dict[str, float] = {}
    for sid, nota in acertos:
        somas[sid] = somas.get(sid, 0.0) + nota
        maiores[sid] = max(maiores.get(sid, 0.0), nota)
    ordem = sorted(somas, key=lambda s: (-maiores[s], -somas[s], s))
    return [Candidata(s, round(somas[s], 4), round(maiores[s], 4)) for s in ordem[:k]]


def posicao(candidatas: list[Candidata], species_id: str, por: str = "maior") -> int | None:
    """Posição (1 = primeira) da espécie ordenando por `soma` ou `maior`."""
    ordem = sorted(candidatas, key=lambda c: (-getattr(c, por), c.species_id))
    for i, c in enumerate(ordem, start=1):
        if c.species_id == species_id:
            return i
    return None


def buscar_especies(
    db: Database,
    vetor: list[float],
    k: int = 10,
    filtro: dict[str, Any] | None = None,
    num_candidatos: int = NUM_CANDIDATOS,
    limite: int = LIMITE_DOCUMENTOS,
) -> list[Candidata]:
    etapa: dict[str, Any] = {
        "index": INDICE_VETOR,
        "path": "embedding",
        "queryVector": vetor,
        "numCandidates": num_candidatos,
        "limit": limite,
    }
    if filtro:
        etapa["filter"] = filtro
    docs = db[SPECIES_RETRIEVAL_DOCS].aggregate(
        [
            {"$vectorSearch": etapa},
            {"$project": {"species_id": 1, "nota": {"$meta": "vectorSearchScore"}}},
        ]
    )
    return agregar(((d["species_id"], d["nota"]) for d in docs), k)


# ---------------------------------------------------------------------------
# Consultas de fumaça
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Consulta(_Base):
    consulta: str = Field(min_length=1)
    esperada: SpeciesId
    dominio: str | None = None
    filtros: dict[str, Any] | None = None


class ConsultasArquivo(_Base):
    versao: str
    top: int = Field(default=10, ge=1)
    consultas: list[Consulta] = Field(min_length=1)


def carregar_consultas(path: Path | str) -> ConsultasArquivo:
    path = Path(path)
    data = _ler_yaml(path)
    try:
        arquivo = ConsultasArquivo.model_validate(data)
    except ValidationError as e:
        raise VocabularioInvalido(path, _erros_pydantic(e)) from e
    erros = [
        f"consultas[{i}].dominio: {c.dominio!r} não é domínio {list(DOMINIOS)}"
        for i, c in enumerate(arquivo.consultas)
        if c.dominio is not None and c.dominio not in DOMINIOS
    ]
    if erros:
        raise VocabularioInvalido(path, erros)
    return arquivo


@dataclass
class ResultadoFumaca:
    top: int
    linhas_consulta: list[tuple[Consulta, list[Candidata], int | None, int | None]] = field(
        default_factory=list
    )
    tokens: int = 0
    relatorio: Path | None = None

    @property
    def falhas(self) -> int:
        return sum(1 for _, _, pos, _ in self.linhas_consulta if pos is None)

    def linhas(self) -> list[str]:
        out = [f"fumaça: {len(self.linhas_consulta)} consultas, top {self.top}"]
        for c, cands, pos, pos_soma in self.linhas_consulta:
            marca = "ok" if pos is not None else "FORA"
            primeiras = ", ".join(x.species_id.removeprefix("sp_") for x in cands[:3])
            out.append(
                f"  [{marca}] {c.consulta!r} -> {c.esperada}: posição {pos or '-'} "
                f"(pela soma: {pos_soma or '-'}; primeiras: {primeiras})"
            )
        out.append(f"  {self.falhas} fora do top {self.top}; {self.tokens} tokens de embedding")
        if self.relatorio:
            out.append(f"  relatório: {self.relatorio}")
        return out


def fumaca(
    db: Database,
    embedder: Embedder,
    modelo: str,
    arquivo: ConsultasArquivo,
    relatorio: Path | None = None,
) -> ResultadoFumaca:
    res = ResultadoFumaca(top=arquivo.top)
    resposta = embedder.embeddings([c.consulta for c in arquivo.consultas], modelo)
    res.tokens = resposta.tokens
    for c, vetor in zip(arquivo.consultas, resposta.vetores, strict=True):
        filtro = dict(c.filtros or {})
        if c.dominio:
            filtro["dominio"] = c.dominio
        # Busca mais espécies do que o top, para a posição pela soma também valer.
        cands = buscar_especies(db, vetor, k=LIMITE_DOCUMENTOS, filtro=filtro or None)
        pos = posicao(cands, c.esperada, "maior")
        pos_soma = posicao(cands, c.esperada, "soma")
        pos = pos if pos is not None and pos <= arquivo.top else None
        pos_soma = pos_soma if pos_soma is not None and pos_soma <= arquivo.top else None
        res.linhas_consulta.append((c, cands[: arquivo.top], pos, pos_soma))

    if relatorio:
        relatorio.parent.mkdir(parents=True, exist_ok=True)
        with relatorio.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n")
            w.writerow(["consulta", "esperada", "posicao_maior", "posicao_soma", "top"])
            for c, cands, pos, pos_soma in res.linhas_consulta:
                top = " ".join(f"{x.species_id}:{x.maior}:{x.soma}" for x in cands)
                w.writerow([c.consulta, c.esperada, pos or "", pos_soma or "", top])
        res.relatorio = relatorio
    return res
