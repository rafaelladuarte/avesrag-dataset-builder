"""raw_* -> species_registry (etapa 2, Especificação > Resolução de nomes).

Um documento por espécie do WikiAves, identificado pelo `species_id` (slug do
nome científico), com a chave de cada fonte (`_id` do doc no `raw_*`, ou o
`speciesCode` no eBird) e o tipo de casamento:

- CBRO, AVONET e BIRDBASE: nome exato. AVONET tenta a aba BirdLife e depois
  a eBird; BIRDBASE tenta as colunas BirdLife, IOC e eBird/Clements.
- eBird, nesta ordem:
  1. `exato`: nome eBird/Clements da linha do BIRDBASE na taxonomia do eBird;
  2. `exato`: nome do WikiAves direto na taxonomia;
  3. `ponte`: correspondência BirdLife -> eBird do AVONET;
  4. `genero`: mesmo epíteto, família equivalente e um único candidato
     (gênero trocado, ex.: Urubitinga urubitinga -> Buteogallus urubitinga).
  As famílias equivalentes (ex.: Rhynchocyclidae no WikiAves = Tyrannidae no
  eBird) saem dos casamentos exatos, sem tabela fixa. Os passos 3 e 4 nunca
  usam um `speciesCode` já atribuído a outra espécie.
- Sem casamento: chave `null` e `sem_match`.

Determinística, sem rede e sem LLM. O `species_id` e o `criado_em` só são
gravados na criação; o resto é recalculado e só é escrito quando muda.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import InsertOne, UpdateOne
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.models import (
    Chaves,
    FonteChave,
    MatchTipo,
    SpeciesRegistry,
    slug_species_id,
)
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import (
    RAW_AVONET,
    RAW_BIRDBASE,
    RAW_CBRO,
    RAW_EBIRD,
    RAW_WIKIAVES,
    SPECIES_REGISTRY,
    garantir_indices,
)
from avesrag_builder.ingest.base import ResultadoIngestao
from avesrag_builder.ingest.wikiaves import COLUNA_EBIRD_BIRDBASE

log = get_logger(__name__)

FONTES: tuple[FonteChave, ...] = ("cbro", "avonet", "birdbase", "ebird")
LOTE = 500

# Ordem da Especificação: BirdLife, IOC, eBird/Clements.
COLUNAS_BIRDBASE = (
    "HBW/BirdLife International (v9.1)",
    "IOC World Bird List (v15.1)",
    COLUNA_EBIRD_BIRDBASE,
)

# Espécies do eBird de Uberlândia que não estão no WikiAves por serem
# domésticas ou exóticas (decisão de 21/11/2026: aparecem no relatório).
DOMESTICAS_EXOTICAS = frozenset(
    {"Alopochen aegyptiaca", "Anser anser", "Anser cygnoides", "Gallus gallus", "Numida meleagris"}
)


def _epiteto(nome: str) -> str:
    return nome.split()[-1]


# ---------------------------------------------------------------------------
# Fontes em memória
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Taxon:
    codigo: str
    nome: str
    familia: str | None
    nome_comum: str | None = None


@dataclass
class Fontes:
    """Índices das raw_* usados no casamento (montados uma vez por execução)."""

    cbro: dict[str, str] = field(default_factory=dict)  # nome -> _id
    avonet_birdlife: set[str] = field(default_factory=set)
    avonet_ebird: set[str] = field(default_factory=set)
    birdbase: dict[str, dict[str, str]] = field(default_factory=dict)  # coluna -> nome -> _id
    birdbase_ebird: dict[str, str] = field(default_factory=dict)  # _id -> nome eBird/Clements
    taxa: dict[str, Taxon] = field(default_factory=dict)  # sciName -> taxon (só species)
    crosswalk: dict[str, set[str]] = field(default_factory=dict)  # BirdLife -> nomes eBird

    def por_codigo(self) -> dict[str, Taxon]:
        return {t.codigo: t for t in self.taxa.values()}


def carregar_fontes(db: Database) -> Fontes:
    f = Fontes()
    for d in db[RAW_CBRO].find({}, {"dados.Nome do táxon (sem autoria)": 1}):
        nome = d["dados"].get("Nome do táxon (sem autoria)")
        if nome:
            f.cbro.setdefault(nome, d["_id"])

    for d in db[RAW_AVONET].find({"_id": {"$regex": "^(birdlife|ebird):"}}, {"_id": 1}):
        aba, nome = d["_id"].split(":", 1)
        (f.avonet_birdlife if aba == "birdlife" else f.avonet_ebird).add(nome)
    for d in db[RAW_AVONET].find(
        {"_id": {"$regex": "^crosswalk:"}}, {"dados.Species1": 1, "dados.Species2": 1}
    ):
        s1, s2 = d["dados"].get("Species1"), d["dados"].get("Species2")
        if s1 and s2:
            f.crosswalk.setdefault(s1, set()).add(s2)

    f.birdbase = {c: {} for c in COLUNAS_BIRDBASE}
    # Sem projeção por coluna: os nomes têm ponto ("(v9.1)"), que o Mongo lê como subcampo.
    for d in db[RAW_BIRDBASE].find({}, {"dados": 1}):
        for c in COLUNAS_BIRDBASE:
            nome = d["dados"].get(c)
            if nome:
                f.birdbase[c].setdefault(nome, d["_id"])
        if d["dados"].get(COLUNA_EBIRD_BIRDBASE):
            f.birdbase_ebird[d["_id"]] = d["dados"][COLUNA_EBIRD_BIRDBASE]

    for d in db[RAW_EBIRD].find(
        {"_id": {"$regex": "^taxon:"}, "dados.category": "species"},
        {"dados.sciName": 1, "dados.speciesCode": 1, "dados.familySciName": 1, "dados.comName": 1},
    ):
        dd = d["dados"]
        f.taxa[dd["sciName"]] = Taxon(
            dd["speciesCode"], dd["sciName"], dd.get("familySciName"), dd.get("comName")
        )
    return f


def carregar_especies(db: Database) -> list[dict[str, Any]]:
    """Linhas da lista do WikiAves (`dados.lista`), ordenadas pelo nome científico."""
    docs = db[RAW_WIKIAVES].find({}, {"dados.lista": 1})
    return sorted((d["dados"]["lista"] for d in docs), key=lambda e: e["nome_cientifico"])


# ---------------------------------------------------------------------------
# Casamento (funções puras)
# ---------------------------------------------------------------------------


def _birdbase(nome: str, f: Fontes) -> str | None:
    for coluna in COLUNAS_BIRDBASE:
        if nome in f.birdbase.get(coluna, {}):
            return f.birdbase[coluna][nome]
    return None


def _avonet(nome: str, f: Fontes) -> str | None:
    if nome in f.avonet_birdlife:
        return f"birdlife:{nome}"
    if nome in f.avonet_ebird:
        return f"ebird:{nome}"
    return None


def ebird_exato(nome: str, birdbase_id: str | None, f: Fontes) -> Taxon | None:
    """Passos 1 e 2: via BIRDBASE eBird/Clements, depois o nome direto."""
    if birdbase_id:
        nome_ebird = f.birdbase_ebird.get(birdbase_id)
        if nome_ebird and nome_ebird in f.taxa:
            return f.taxa[nome_ebird]
    return f.taxa.get(nome)


def equivalencias_familia(especies: list[dict[str, Any]], f: Fontes) -> set[tuple[str, str]]:
    """Pares (família WikiAves, família eBird) vistos nos casamentos exatos."""
    pares: set[tuple[str, str]] = set()
    for e in especies:
        taxon = ebird_exato(e["nome_cientifico"], _birdbase(e["nome_cientifico"], f), f)
        if taxon and taxon.familia and e.get("familia"):
            pares.add((e["familia"], taxon.familia))
    return pares


def ebird_aproximado(
    nome: str,
    familia: str | None,
    f: Fontes,
    familias: set[tuple[str, str]],
    usados: set[str],
) -> tuple[Taxon, MatchTipo] | None:
    """Passos 3 (`ponte`) e 4 (`genero`); ignora códigos já atribuídos."""
    ponte = {f.taxa[n] for n in f.crosswalk.get(nome, set()) if n in f.taxa}
    ponte = {t for t in ponte if t.codigo not in usados}
    if len(ponte) == 1:
        return ponte.pop(), "ponte"

    epiteto = _epiteto(nome)
    candidatos = [
        t
        for t in f.taxa.values()
        if _epiteto(t.nome) == epiteto
        and t.nome != nome
        and t.codigo not in usados
        and familia is not None
        and (familia, t.familia) in familias
    ]
    if len(candidatos) == 1:
        return candidatos[0], "genero"
    return None


def resolver(
    especie: dict[str, Any],
    f: Fontes,
    agora: datetime,
    taxon_ebird: tuple[Taxon, MatchTipo] | None,
) -> SpeciesRegistry:
    """Monta o registro de uma espécie; o eBird vem já resolvido (precisa do conjunto)."""
    nome = especie["nome_cientifico"]
    chaves: dict[str, str | None] = {
        "wikiaves": str(especie["id"]),
        "cbro": f.cbro.get(nome),
        "avonet": _avonet(nome, f),
        "birdbase": _birdbase(nome, f),
        "ebird": taxon_ebird[0].codigo if taxon_ebird else None,
    }
    match: dict[str, MatchTipo] = {
        fonte: "sem_match" if chaves[fonte] is None else "exato" for fonte in FONTES
    }
    if taxon_ebird:
        match["ebird"] = taxon_ebird[1]
    return SpeciesRegistry(
        species_id=slug_species_id(nome),
        nome_cientifico=nome,
        nome_comum=especie.get("nome_comum") or None,
        chaves=Chaves(**chaves),
        match=match,
        criado_em=agora,
        atualizado_em=agora,
    )


def resolver_todas(
    especies: list[dict[str, Any]], f: Fontes, agora: datetime | None = None
) -> list[SpeciesRegistry]:
    """Resolve todas as espécies: primeiro os casamentos exatos, depois os aproximados."""
    agora = agora or datetime.now(UTC)
    exatos: dict[str, Taxon] = {}
    for e in especies:
        nome = e["nome_cientifico"]
        taxon = ebird_exato(nome, _birdbase(nome, f), f)
        if taxon:
            exatos[nome] = taxon

    repetidos = [c for c, n in Counter(t.codigo for t in exatos.values()).items() if n > 1]
    if repetidos:
        log.warning(f"speciesCode em mais de uma espécie do WikiAves: {repetidos}")

    familias = equivalencias_familia(especies, f)
    usados = {t.codigo for t in exatos.values()}
    registros = []
    for e in especies:
        nome = e["nome_cientifico"]
        if nome in exatos:
            ebird: tuple[Taxon, MatchTipo] | None = (exatos[nome], "exato")
        else:
            ebird = ebird_aproximado(nome, e.get("familia"), f, familias, usados)
            if ebird:
                usados.add(ebird[0].codigo)
        registros.append(resolver(e, f, agora, ebird))
    return registros


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------

CAMPOS_RECALCULADOS = ("nome_cientifico", "nome_comum", "chaves", "match")


def gravar(db: Database, registros: list[SpeciesRegistry]) -> ResultadoIngestao:
    """Upsert pelo `species_id`; só escreve o que mudou. Não apaga órfãos."""
    garantir_indices(db)
    col = db[SPECIES_REGISTRY]
    resultado = ResultadoIngestao(fonte="resolve", collection=SPECIES_REGISTRY)
    existentes = {
        d["species_id"]: d
        for d in col.find({}, {"_id": 0, **dict.fromkeys(CAMPOS_RECALCULADOS, 1), "species_id": 1})
    }

    ops: list[InsertOne | UpdateOne] = []
    for reg in registros:
        doc = reg.to_mongo()
        atual = existentes.get(reg.species_id)
        if atual is None:
            ops.append(InsertOne(doc))
            resultado.inseridos += 1
            continue
        novos = {k: doc[k] for k in CAMPOS_RECALCULADOS}
        if all(atual.get(k) == v for k, v in novos.items()):
            resultado.inalterados += 1
            continue
        ops.append(
            UpdateOne(
                {"species_id": reg.species_id},
                {"$set": {**novos, "atualizado_em": doc["atualizado_em"]}},
            )
        )
        resultado.atualizados += 1

    for i in range(0, len(ops), LOTE):
        col.bulk_write(ops[i : i + LOTE], ordered=False)

    ids = {r.species_id for r in registros}
    resultado.ausentes_na_fonte = sum(1 for sid in existentes if sid not in ids)
    return resultado


# ---------------------------------------------------------------------------
# Piloto e relatórios
# ---------------------------------------------------------------------------


def codigos_do_municipio(db: Database, geocodigo: str) -> list[str]:
    municipio = db[RAW_EBIRD].find_one({"_id": f"municipio:{geocodigo}"}, {"dados.especies": 1})
    if not municipio:
        raise ValueError(f"raw_ebird não tem o município {geocodigo}: rode `ingest ebird --piloto`")
    return list(municipio["dados"].get("especies") or [])


def especies_do_piloto(db: Database, geocodigo: str | None = None) -> list[str]:
    """`species_id` do registry com registro no eBird do município do piloto."""
    geocodigo = geocodigo or get_settings().PILOTO_MUNICIPIO_IBGE
    codigos = codigos_do_municipio(db, geocodigo)
    docs = db[SPECIES_REGISTRY].find({"chaves.ebird": {"$in": codigos}}, {"species_id": 1})
    return sorted(d["species_id"] for d in docs)


@dataclass
class Cobertura:
    total: int
    por_fonte: dict[str, int]
    piloto_codigos: int
    piloto_no_registry: int

    @property
    def piloto_pct(self) -> float:
        return 100 * self.piloto_no_registry / self.piloto_codigos if self.piloto_codigos else 0.0

    def linhas(self) -> list[str]:
        out = [f"{self.total} espécies no registry"]
        for fonte, n in self.por_fonte.items():
            out.append(f"  {fonte}: {n} ({100 * n / self.total:.1f}%)" if self.total else fonte)
        out.append(
            f"  piloto: {self.piloto_no_registry} de {self.piloto_codigos} espécies do eBird "
            f"do município ({self.piloto_pct:.1f}%)"
        )
        return out


def _tsv(caminho: Path, cabecalho: list[str], linhas: list[list[Any]]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(cabecalho)
        w.writerows(linhas)


def relatorios(
    db: Database,
    registros: list[SpeciesRegistry],
    f: Fontes,
    settings: Settings,
) -> Cobertura:
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sem_match = [
        [fonte, r.species_id, r.nome_cientifico]
        for r in registros
        for fonte in FONTES
        if r.match[fonte] == "sem_match"
    ]
    _tsv(
        settings.REPORTS_DIR / "resolve_sem_match.tsv",
        ["fonte", "species_id", "nome_cientifico"],
        sem_match,
    )

    codigos = codigos_do_municipio(db, settings.PILOTO_MUNICIPIO_IBGE)
    por_codigo = {r.chaves.ebird: r for r in registros if r.chaves.ebird}
    taxa = f.por_codigo()
    piloto: list[list[Any]] = []
    for codigo in sorted(codigos, key=lambda c: taxa[c].nome if c in taxa else c):
        t = taxa.get(codigo)
        r = por_codigo.get(codigo)
        nome, comum = (t.nome, t.nome_comum) if t else (codigo, None)
        if r is None:
            motivo = "domestica_exotica" if nome in DOMESTICAS_EXOTICAS else "sem_casamento"
            piloto.append([codigo, nome, comum, motivo, ""])
        elif r.match["ebird"] != "exato":
            piloto.append([codigo, nome, comum, r.match["ebird"], r.species_id])
    _tsv(
        settings.REPORTS_DIR / "resolve_piloto.tsv",
        ["speciesCode", "sciName", "comName", "motivo", "species_id"],
        piloto,
    )

    ids = {r.species_id for r in registros}
    orfaos = sorted(
        d["species_id"]
        for d in db[SPECIES_REGISTRY].find({}, {"species_id": 1})
        if d["species_id"] not in ids
    )
    (settings.REPORTS_DIR / "resolve_orfaos.txt").write_text(
        "".join(f"{s}\n" for s in orfaos), encoding="utf-8"
    )

    return Cobertura(
        total=len(registros),
        por_fonte={
            fonte: sum(r.match[fonte] != "sem_match" for r in registros) for fonte in FONTES
        },
        piloto_codigos=len(set(codigos)),
        piloto_no_registry=sum(1 for c in set(codigos) if c in por_codigo),
    )


def executar(db: Database, settings: Settings | None = None) -> tuple[ResultadoIngestao, Cobertura]:
    settings = settings or get_settings()
    especies = carregar_especies(db)
    if not especies:
        raise ValueError("raw_wikiaves está vazia: rode `ingest wikiaves` antes")
    fontes = carregar_fontes(db)
    registros = resolver_todas(especies, fontes)
    resultado = gravar(db, registros)
    cobertura = relatorios(db, registros, fontes, settings)
    log.info(resultado.resumo())
    return resultado, cobertura
