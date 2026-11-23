"""Espécies do escopo e os nomes científicos para buscar nas fontes de foto.

As fontes de foto (Commons, iNaturalist) não têm lista própria de espécies do
Brasil: a busca parte do registry. Por isso elas rodam depois do `resolve`.
Cada espécie leva o nome do eBird (taxonomia mais próxima das duas fontes) e o
do WikiAves, nessa ordem e sem repetir.
"""

from __future__ import annotations

from dataclasses import dataclass

from pymongo.database import Database

from avesrag_builder.db.collections import RAW_EBIRD, SPECIES_REGISTRY
from avesrag_builder.resolve.registry import especies_do_piloto


@dataclass(frozen=True)
class EspecieEscopo:
    species_id: str
    nomes: tuple[str, ...]  # eBird primeiro, depois WikiAves


class RegistryVazio(ValueError):
    """As fontes de foto precisam do species_registry: rode `resolve` antes."""


def especies_com_nomes(
    db: Database, piloto: bool = False, geocodigo: str | None = None
) -> list[EspecieEscopo]:
    filtro: dict = {}
    if piloto:
        filtro = {"species_id": {"$in": especies_do_piloto(db, geocodigo)}}
    docs = list(
        db[SPECIES_REGISTRY].find(
            filtro, {"species_id": 1, "nome_cientifico": 1, "chaves.ebird": 1}
        )
    )
    if not docs:
        raise RegistryVazio(
            "species_registry vazio"
            + (" no escopo do piloto" if piloto else "")
            + ": rode `resolve` antes"
        )

    nomes = nomes_por_especie(db, docs)
    return [EspecieEscopo(sid, nomes[sid]) for sid in sorted(nomes)]


def nomes_por_especie(db: Database, registros: list[dict]) -> dict[str, tuple[str, ...]]:
    """species_id -> nomes para buscar nas fontes de foto (eBird, depois WikiAves).

    Usada pela ingestão (o que consultar) e pelo `fuse` (como casar): os dois
    precisam dos mesmos nomes. `registros` são docs do species_registry com
    `species_id`, `nome_cientifico` e `chaves.ebird`.
    """
    codigos = [c for d in registros if (c := (d.get("chaves") or {}).get("ebird"))]
    nome_ebird = {
        t["_id"].removeprefix("taxon:"): t["dados"]["sciName"]
        for t in db[RAW_EBIRD].find(
            {"_id": {"$in": [f"taxon:{c}" for c in codigos]}}, {"dados.sciName": 1}
        )
    }
    out = {}
    for d in registros:
        candidatos = [nome_ebird.get((d.get("chaves") or {}).get("ebird")), d["nome_cientifico"]]
        out[d["species_id"]] = tuple(
            dict.fromkeys(n.strip() for n in candidatos if n and n.strip())
        )
    return out
