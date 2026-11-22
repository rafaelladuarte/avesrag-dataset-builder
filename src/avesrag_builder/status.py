"""`avesrag-builder status`: o estado de cada etapa e o próximo passo.

Só lê o banco: não grava nada, não chama API e não precisa de chave. Serve para
quem está reproduzindo o piloto confirmar o resultado e saber onde parou.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pymongo.database import Database

from avesrag_builder.db.collections import (
    LLM_BATCHES,
    RAW_AVONET,
    RAW_BIRDBASE,
    RAW_CBRO,
    RAW_EBIRD,
    RAW_IBGE,
    RAW_WIKIAVES,
    SPECIES,
    SPECIES_EXTRACTIONS,
    SPECIES_REGISTRY,
    SPECIES_RETRIEVAL_DOCS,
)
from avesrag_builder.docs.indices import INDICE_TEXTO, INDICE_VETOR

PROMPTS = 3
PLANILHAS = ("cbro", "ibge", "birdbase", "avonet")


@dataclass
class Estado:
    piloto: bool
    raw: dict[str, int] = field(default_factory=dict)  # fonte -> documentos
    ebird_municipios: int = 0
    wikiaves_paginas: int = 0
    registry: int = 0
    piloto_codigos: int = 0  # espécies do eBird no município do piloto
    escopo: int = 0  # espécies do registry no escopo
    escopo_com_pagina: int = 0
    pares: int = 0
    pares_validos: int = 0
    pares_sem_texto: int = 0
    lotes_abertos: int = 0
    fichas: int = 0
    dq: dict[str, int] = field(default_factory=dict)
    sem_dq: int = 0
    documentos: int = 0
    especies_com_documento: int = 0
    indices: dict[str, str] = field(default_factory=dict)  # nome -> status

    @property
    def aptas(self) -> int:
        return self.dq.get("apta", 0)

    @property
    def pct_aptas(self) -> float:
        return 100 * self.aptas / self.fichas if self.fichas else 0.0

    @property
    def pares_esperados(self) -> int:
        return self.escopo * PROMPTS


def _flag(piloto: bool) -> str:
    return " --piloto" if piloto else ""


def proximo_passo(e: Estado) -> str | None:
    """Primeira etapa incompleta, na ordem do pipeline (None = tudo pronto)."""
    p = _flag(e.piloto)
    faltam = [f for f in PLANILHAS if not e.raw.get(f)]
    if faltam:
        return f"ingest {faltam[0]}"
    if e.ebird_municipios == 0:
        return "ingest ebird" + p
    if e.wikiaves_paginas == 0:
        return "ingest wikiaves" + p
    if e.registry == 0:
        return "resolve"
    if e.escopo_com_pagina < e.escopo:
        return "ingest wikiaves" + p + " (faltam páginas de espécies do escopo)"
    if e.lotes_abertos:
        return f"extract{p} --sem-esperar (lote em andamento; rode de novo mais tarde)"
    if e.pares < e.pares_esperados:
        return "extract" + p
    if e.fichas < e.escopo:
        return "fuse" + p
    if e.sem_dq:
        return "validate" + p
    if e.aptas and e.especies_com_documento < e.aptas:
        return "docs" + p
    if e.documentos and any(e.indices.get(n) != "READY" for n in (INDICE_VETOR, INDICE_TEXTO)):
        return "index"
    return None


def linhas(e: Estado) -> list[str]:
    raw = " · ".join(f"{f} {e.raw.get(f, 0)}" for f in PLANILHAS)
    out = [
        f"raw_*: {raw} · ebird {e.ebird_municipios} município(s) · "
        f"wikiaves {e.raw.get('wikiaves', 0)} ({e.wikiaves_paginas} páginas)",
        f"species_registry: {e.registry} espécies"
        + (
            f"; piloto {e.escopo} de {e.piloto_codigos} do eBird "
            f"({100 * e.escopo / e.piloto_codigos:.1f}%)"
            if e.piloto and e.piloto_codigos
            else f"; escopo {e.escopo}"
        ),
        f"species_extractions: {e.pares} de {e.pares_esperados} pares; "
        f"{e.pares_validos} válidas, {e.pares_sem_texto} sem texto; {e.lotes_abertos} lote(s) aberto(s)",
        f"species: {e.fichas} fichas; apta {e.aptas} ({e.pct_aptas:.1f}%), "
        f"incompleta {e.dq.get('incompleta', 0)}, bloqueada {e.dq.get('bloqueada', 0)}"
        + (f", sem classificação {e.sem_dq}" if e.sem_dq else ""),
        f"species_retrieval_docs: {e.documentos} documentos de {e.especies_com_documento} espécies; "
        + ", ".join(f"{n} {e.indices.get(n, 'ausente')}" for n in (INDICE_VETOR, INDICE_TEXTO)),
    ]
    passo = proximo_passo(e)
    out.append(
        f"próximo passo: avesrag-builder {passo}"
        if passo
        else "próximo passo: nenhum, o escopo está completo"
    )
    return out


def coletar(db: Database, piloto: bool, geocodigo: str) -> Estado:
    from avesrag_builder.resolve.registry import codigos_do_municipio, especies_do_piloto

    e = Estado(piloto=piloto)
    for fonte, col in (
        ("cbro", RAW_CBRO),
        ("ibge", RAW_IBGE),
        ("birdbase", RAW_BIRDBASE),
        ("avonet", RAW_AVONET),
        ("wikiaves", RAW_WIKIAVES),
    ):
        e.raw[fonte] = db[col].estimated_document_count()
    e.ebird_municipios = db[RAW_EBIRD].count_documents({"_id": {"$regex": "^municipio:"}})
    e.wikiaves_paginas = db[RAW_WIKIAVES].count_documents({"dados.pagina": {"$type": "object"}})
    e.registry = db[SPECIES_REGISTRY].estimated_document_count()
    if e.registry == 0:
        return e

    if piloto:
        try:
            e.piloto_codigos = len(set(codigos_do_municipio(db, geocodigo)))
            ids = especies_do_piloto(db, geocodigo)
        except ValueError:  # raw_ebird sem o município do piloto
            ids = []
    else:
        ids = [d["species_id"] for d in db[SPECIES_REGISTRY].find({}, {"species_id": 1})]
    e.escopo = len(ids)
    no_escopo = {"species_id": {"$in": ids}}

    chaves = [
        d["chaves"]["wikiaves"]
        for d in db[SPECIES_REGISTRY].find(no_escopo, {"chaves.wikiaves": 1})
    ]
    e.escopo_com_pagina = db[RAW_WIKIAVES].count_documents(
        {"_id": {"$in": chaves}, "dados.pagina": {"$type": "object"}}
    )

    ext = db[SPECIES_EXTRACTIONS]
    e.pares = ext.count_documents(no_escopo)
    e.pares_validos = ext.count_documents({**no_escopo, "validacao.ok": True})
    e.pares_sem_texto = ext.count_documents({**no_escopo, "validacao.erro": "sem_texto"})
    e.lotes_abertos = db[LLM_BATCHES].count_documents({"status": "enviado"})

    for d in db[SPECIES].find(no_escopo, {"_meta.dq_status": 1}):
        status = (d.get("_meta") or {}).get("dq_status")
        e.fichas += 1
        if status:
            e.dq[status] = e.dq.get(status, 0) + 1
        else:
            e.sem_dq += 1

    docs = db[SPECIES_RETRIEVAL_DOCS]
    e.documentos = docs.count_documents(no_escopo)
    e.especies_com_documento = len(docs.distinct("species_id", no_escopo))
    if SPECIES_RETRIEVAL_DOCS in db.list_collection_names():
        e.indices = {i["name"]: i.get("status", "?") for i in docs.list_search_indexes()}
    return e
