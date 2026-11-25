"""Etapa 4 (`fuse`): registry + extractions + raw_* -> species_occurrence e species.

1. Recalcula `species_occurrence` a partir de `raw_ebird` + `raw_ibge`.
2. Carrega de uma vez, para as espécies do escopo, o registry, os `raw_*` pelas
   chaves do registry e as extrações.
3. Monta a ficha de cada espécie com as regras de `fuse/regras.py`, cada campo
   com a sua entrada no `_prov`.
4. Compara com a ficha gravada sem o `_meta` e só grava o que mudou. Ao gravar,
   `built_at` vira agora e o `dq_status` sai (o `validate` reclassifica). Sem
   mudança, nada é escrito e o `dq_status` continua valendo.

Sem chamadas externas. Fichas de espécies fora do registry não são apagadas;
o relatório lista essas órfãs.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pymongo import InsertOne, ReplaceOne
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.models import Atributos, Meta, Prov, Species
from avesrag_builder.core.regras_ficha import RegrasFicha, regras_ficha_padrao
from avesrag_builder.core.regras_fusao import RegrasFusao, regras_fusao_padrao
from avesrag_builder.core.regras_midia import RegrasMidia, regras_midia_padrao
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.core.vocabulario import (
    RegrasBico,
    Vocabulario,
    regras_bico_padrao,
    vocabulario_padrao,
)
from avesrag_builder.db.collections import (
    RAW_AVONET,
    RAW_BIRDALBUM,
    RAW_BIRDBASE,
    RAW_CBRO,
    RAW_COMMONS,
    RAW_INATURALIST,
    RAW_WIKIAVES,
    SPECIES,
    SPECIES_EXTRACTIONS,
    SPECIES_REGISTRY,
    garantir_indices,
)
from avesrag_builder.fuse import regras as r
from avesrag_builder.fuse import species_occurrence
from avesrag_builder.ingest.base import ResultadoIngestao
from avesrag_builder.ingest.escopo import nomes_por_especie
from avesrag_builder.resolve.registry import especies_do_piloto

log = get_logger(__name__)

LOTE = 500

# Campos que têm reserva: o relatório mostra de onde cada um veio.
CAMPOS_COM_RESERVA = (
    "nomes.en",
    "taxonomia",
    "iucn",
    "atributos.tamanho",
    "atributos.bico_tipo",
    "atributos.ambiente",
    "atributos.onde_estava",
    "atributos.grupo",
    "midia.foto",
    "midia.fotos",
    "midia.ilustracao",
    "perfil.massa_g",
    "perfil.dieta",
)


# ---------------------------------------------------------------------------
# Escopo e carga
# ---------------------------------------------------------------------------


def escopo(db: Database, piloto: bool) -> list[str]:
    if piloto:
        return especies_do_piloto(db)
    return sorted(d["species_id"] for d in db[SPECIES_REGISTRY].find({}, {"species_id": 1}))


def _por_id(db: Database, collection: str, ids: list[str]) -> dict[str, dict[str, Any]]:
    ids = [i for i in ids if i]
    return {d["_id"]: d["dados"] for d in db[collection].find({"_id": {"$in": ids}})}


def carregar(
    db: Database, ids: list[str], ocorrencias: dict[str, dict[str, Any]]
) -> list[r.DadosEspecie]:
    registros = list(db[SPECIES_REGISTRY].find({"species_id": {"$in": ids}}))
    chaves = [reg["chaves"] for reg in registros]
    raw = {
        fonte: _por_id(db, col, [c.get(fonte) for c in chaves])
        for fonte, col in (
            ("wikiaves", RAW_WIKIAVES),
            ("cbro", RAW_CBRO),
            ("avonet", RAW_AVONET),
            ("birdbase", RAW_BIRDBASE),
        )
    }
    extracoes: dict[str, dict[str, dict[str, Any]]] = {}
    for doc in db[SPECIES_EXTRACTIONS].find({"species_id": {"$in": ids}}):
        extracoes.setdefault(doc["species_id"], {})[doc["prompt"]] = doc

    # Bird Album: pelo código do eBird (a taxonomia da AviList difere da do WikiAves
    # em ~3% do piloto) e, sem código, pelo nome científico.
    codigos = [c.get("ebird") for c in chaves if c.get("ebird")]
    nomes = [reg["nome_cientifico"] for reg in registros]
    album_ebird: dict[str, dict[str, Any]] = {}
    album_nome: dict[str, dict[str, Any]] = {}
    for doc in db[RAW_BIRDALBUM].find(
        {"$or": [{"dados.ebird": {"$in": codigos}}, {"dados.scientific_name": {"$in": nomes}}]}
    ):
        dados_album = doc["dados"]
        if dados_album.get("ebird"):
            album_ebird.setdefault(dados_album["ebird"], dados_album)
        album_nome.setdefault(dados_album.get("scientific_name"), dados_album)

    # Fotos: pelos mesmos nomes que a ingestão consultou (eBird, depois WikiAves).
    nomes_foto = nomes_por_especie(db, registros)
    todos = sorted({n for ns in nomes_foto.values() for n in ns})
    fotos = {fonte: _por_nome(db, col, todos) for fonte, col in FONTES_FOTO}

    dados = []
    for reg in sorted(registros, key=lambda x: x["species_id"]):
        sid, ch = reg["species_id"], reg["chaves"]
        album = album_ebird.get(ch.get("ebird") or "")
        album_por = "ebird" if album else None
        if album is None and reg["nome_cientifico"] in album_nome:
            album, album_por = album_nome[reg["nome_cientifico"]], "nome"
        dados.append(
            r.DadosEspecie(
                species_id=sid,
                nome_cientifico=reg["nome_cientifico"],
                nome_comum=reg.get("nome_comum"),
                wikiaves=raw["wikiaves"].get(ch.get("wikiaves")) or {},
                cbro=raw["cbro"].get(ch.get("cbro")),
                avonet=raw["avonet"].get(ch.get("avonet")),
                birdbase=raw["birdbase"].get(ch.get("birdbase")),
                extracoes=extracoes.get(sid, {}),
                ocorrencia=ocorrencias.get(sid),
                birdalbum=album,
                birdalbum_por=album_por,
                inaturalist=_primeiro(fotos["inaturalist"], nomes_foto[sid]),
                commons=_primeiro(fotos["commons"], nomes_foto[sid]),
            )
        )
    return dados


FONTES_FOTO = (("inaturalist", RAW_INATURALIST), ("commons", RAW_COMMONS))


def _por_nome(db: Database, collection: str, nomes: list[str]) -> dict[str, dict[str, Any]]:
    """nome -> `dados` do primeiro documento (menor `_id`) que traz o nome em `dados.nomes`."""
    out: dict[str, dict[str, Any]] = {}
    for doc in db[collection].find({"dados.nomes": {"$in": nomes}}).sort("_id", 1):
        for nome in doc["dados"].get("nomes", []):
            out.setdefault(nome, doc["dados"])
    return out


def _primeiro(por_nome: dict[str, dict[str, Any]], nomes: tuple[str, ...]) -> dict | None:
    return next((por_nome[n] for n in nomes if n in por_nome), None)


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------


@dataclass
class Ficha:
    species: Species
    descartes: r.Descartes


def montar(
    d: r.DadosEspecie,
    vocab: Vocabulario,
    bico: RegrasBico,
    regras: RegrasFusao,
    agora: datetime | None = None,
    birdalbum: tuple[str, str] | None = None,
    midia_regras: RegrasMidia | None = None,
    ficha_regras: RegrasFicha | None = None,
) -> Ficha:
    """Ficha de uma espécie. Levanta `ValidationError` se faltar o nome em português.

    `birdalbum` é (repositório, commit) das ilustrações; sem ele, vale o do settings.
    `midia_regras` escolhe a foto; sem ele, vale o `config/regras_midia.yaml`.
    """
    midia_regras = midia_regras or regras_midia_padrao()
    ficha_regras = ficha_regras or regras_ficha_padrao()
    if birdalbum is None:
        s = get_settings()
        birdalbum = (s.BIRDALBUM_REPO, s.BIRDALBUM_REF)
    descartes = r.Descartes()
    prov: dict[str, Prov] = {}
    doc: dict[str, Any] = {"species_id": d.species_id, "nome_cientifico": d.nome_cientifico}

    def usar(caminho: str, campo: r.Campo | None) -> Any:
        if campo is None:
            return None
        prov[caminho] = campo.prov
        return campo.valor

    nomes = {"pt": usar("nomes.pt", r.nomes_pt(d)), "en": usar("nomes.en", r.nomes_en(d))}
    doc["nomes"] = {k: v for k, v in nomes.items() if v}
    tax = r.taxonomia(d)
    doc["taxonomia"] = usar("taxonomia", tax) or {}
    doc["status_ocorrencia"] = usar("status_ocorrencia", r.status_ocorrencia(d))
    doc["iucn"] = usar("iucn", r.iucn(d, vocab))
    doc["ocorrencia"] = usar("ocorrencia", r.ocorrencia(d))
    midia = usar("midia", r.midia(d)) or {}
    foto = usar("midia.foto", r.foto(d, midia_regras))
    if foto:
        midia = {**midia, "foto": foto}
        fotos = usar("midia.fotos", r.galeria(d, foto, midia_regras))
        if fotos:
            midia = {**midia, "fotos": fotos}
    ilustracao = usar("midia.ilustracao", r.ilustracao(d, *birdalbum))
    if ilustracao:
        midia = {**midia, "ilustracao": ilustracao}
    doc["midia"] = midia or None
    perfil = {
        "massa_g": usar("perfil.massa_g", r.massa(d)),
        "dieta": usar("perfil.dieta", r.dieta(d, ficha_regras)),
    }
    doc["perfil"] = {k: v for k, v in perfil.items() if v is not None} or None

    comprimento = r.comprimento_cm(d, regras, descartes)
    por_parte = r.cores_por_parte(d, vocab, descartes)
    familia = tax.valor["familia"] if tax else None
    campos = {
        "comprimento_cm": comprimento,
        "tamanho": r.tamanho(d, comprimento, regras, vocab),
        "cores": r.cores(d, por_parte, vocab, descartes),
        "cores_por_parte": por_parte,
        "marcas": r.lista_llm(d, r.B01, "marcas", vocab, descartes),
        "bico_tipo": r.bico_tipo(d, familia, bico),
        "cauda": r.lista_llm(d, r.B01, "cauda", vocab, descartes),
        "ambiente": r.ambiente(d, vocab, descartes),
        "onde_estava": r.onde_estava(d, vocab, descartes),
        "o_que_fazia": r.lista_llm(d, r.B02, "o_que_fazia", vocab, descartes),
        "grupo": r.grupo(d, vocab, descartes),
        "atividade": r.lista_llm(d, r.B02, "atividade", vocab, descartes),
    }
    doc["atributos"] = {nome: usar(f"atributos.{nome}", c) for nome, c in campos.items()}
    doc["_prov"] = prov
    doc["_meta"] = Meta(built_at=agora or datetime.now(UTC))
    return Ficha(species=Species.model_validate(doc), descartes=descartes)


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------


def _conteudo(doc: dict[str, Any]) -> dict[str, Any]:
    """O que a comparação considera: tudo menos `_id` e `_meta`."""
    return {k: v for k, v in doc.items() if k not in ("_id", "_meta")}


def gravar(db: Database, fichas: list[Species]) -> ResultadoIngestao:
    garantir_indices(db)
    col = db[SPECIES]
    resultado = ResultadoIngestao(fonte="fuse", collection=SPECIES)
    ids = [f.species_id for f in fichas]
    existentes = {d["species_id"]: d for d in col.find({"species_id": {"$in": ids}})}
    ops: list[InsertOne | ReplaceOne] = []
    for ficha in fichas:
        doc = ficha.to_mongo()
        atual = existentes.get(ficha.species_id)
        if atual is None:
            ops.append(InsertOne(doc))
            resultado.inseridos += 1
        elif _conteudo(atual) == _conteudo(doc):
            resultado.inalterados += 1
        else:
            # Sem `_id` no doc novo, o ReplaceOne mantém o ObjectId; o dq_status sai.
            ops.append(ReplaceOne({"species_id": ficha.species_id}, doc))
            resultado.atualizados += 1
    for i in range(0, len(ops), LOTE):
        col.bulk_write(ops[i : i + LOTE], ordered=False)
    return resultado


# ---------------------------------------------------------------------------
# Execução e relatório
# ---------------------------------------------------------------------------


@dataclass
class ResultadoFuse:
    escopo: int = 0
    species: ResultadoIngestao | None = None
    ocorrencia: ResultadoIngestao | None = None
    codigos_ebird_sem_especie: int = 0
    erros: list[tuple[str, str]] = field(default_factory=list)  # (species_id, erro)
    cobertura: Counter[str] = field(default_factory=Counter)
    origens: dict[str, Counter[str]] = field(default_factory=dict)  # campo -> fonte/metodo
    descartes: Counter[str] = field(default_factory=Counter)  # prompt -> itens descartados
    orfas: list[str] = field(default_factory=list)
    relatorio: Path | None = None

    def linhas(self) -> list[str]:
        n = self.escopo
        out = [f"fuse: {n} espécies no escopo"]
        if self.ocorrencia:
            out.append(
                f"  {self.ocorrencia.resumo()}; {self.codigos_ebird_sem_especie} "
                "speciesCode do eBird sem espécie no registry"
            )
        if self.species:
            out.append(f"  {self.species.resumo()}")
        if self.erros:
            out.append(f"  {len(self.erros)} espécies com erro (ver o relatório)")
        out.append("  cobertura:")
        for campo, qtd in self.cobertura.items():
            pct = 100 * qtd / n if n else 0.0
            origem = self.origens.get(campo)
            detalhe = (
                f" [{', '.join(f'{k} {v}' for k, v in origem.most_common())}]" if origem else ""
            )
            out.append(f"    {campo}: {qtd} ({pct:.1f}%){detalhe}")
        descartes = ", ".join(f"{p} {q}" for p, q in sorted(self.descartes.items())) or "nenhum"
        out.append(f"  itens descartados por evidência não encontrada: {descartes}")
        if self.orfas:
            out.append(f"  {len(self.orfas)} fichas em species sem espécie no registry")
        if self.relatorio:
            out.append(f"  relatório: {self.relatorio}")
        return out


def _licenca_foto(species: Species) -> str:
    foto = species.midia.foto if species.midia else None
    return foto.licenca if foto else ""


def _origem(p: Prov) -> str:
    return f"{p.fonte}/{p.metodo}" if p.metodo else p.fonte


CAMPOS_COBERTURA = (
    "nomes.en",
    "taxonomia",
    "status_ocorrencia",
    "iucn",
    "ocorrencia",
    "midia",
    "midia.foto",
    "midia.ilustracao",
    *(f"atributos.{c}" for c in Atributos.model_fields),
)


def _relatorio(
    caminho: Path, fichas: list[Ficha], erros: list[tuple[str, str]], res: ResultadoFuse
) -> None:
    for ficha in fichas:
        prov = ficha.species.prov
        for campo in CAMPOS_COBERTURA:
            if campo in prov:
                res.cobertura[campo] += 1
                if campo in CAMPOS_COM_RESERVA:
                    res.origens.setdefault(campo, Counter())[_origem(prov[campo])] += 1
            else:
                res.cobertura.setdefault(campo, 0)
        res.descartes.update(ficha.descartes.por_prompt)

    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            [
                "species_id",
                "n_campos",
                *CAMPOS_COM_RESERVA,
                "foto_licenca",
                "descartes_b01",
                "descartes_b02",
                "erro",
            ]
        )
        for ficha in fichas:
            prov = ficha.species.prov
            w.writerow(
                [
                    ficha.species.species_id,
                    len(prov),
                    *(_origem(prov[c]) if c in prov else "" for c in CAMPOS_COM_RESERVA),
                    _licenca_foto(ficha.species),
                    ficha.descartes.por_prompt.get(r.B01, 0),
                    ficha.descartes.por_prompt.get(r.B02, 0),
                    "",
                ]
            )
        for sid, erro in erros:
            w.writerow([sid, 0, *([""] * len(CAMPOS_COM_RESERVA)), "", 0, 0, erro])


def executar(
    db: Database,
    piloto: bool = False,
    settings: Settings | None = None,
    vocab: Vocabulario | None = None,
    bico: RegrasBico | None = None,
    regras: RegrasFusao | None = None,
    midia_regras: RegrasMidia | None = None,
    ficha_regras: RegrasFicha | None = None,
) -> ResultadoFuse:
    settings = settings or get_settings()
    midia_regras = midia_regras or regras_midia_padrao()
    ficha_regras = ficha_regras or regras_ficha_padrao()
    vocab = vocab or vocabulario_padrao()
    bico = bico or regras_bico_padrao()
    regras = regras or regras_fusao_padrao()

    ids = escopo(db, piloto)
    if not ids:
        raise ValueError("nenhuma espécie no escopo: rode `resolve` antes")
    res = ResultadoFuse(escopo=len(ids))

    ocorrencias, res.ocorrencia = species_occurrence.executar(db)
    res.codigos_ebird_sem_especie = len(ocorrencias.codigos_sem_especie)
    por_especie = {sid: occ.to_mongo() for sid, occ in ocorrencias.por_especie.items()}

    agora = datetime.now(UTC)
    birdalbum = (settings.BIRDALBUM_REPO, settings.BIRDALBUM_REF)
    fichas: list[Ficha] = []
    for d in carregar(db, ids, por_especie):
        try:
            fichas.append(
                montar(d, vocab, bico, regras, agora, birdalbum, midia_regras, ficha_regras)
            )
        except ValidationError as e:
            res.erros.append((d.species_id, str(e).replace("\n", " ")))
    res.species = gravar(db, [f.species for f in fichas])

    registrados = {d["species_id"] for d in db[SPECIES_REGISTRY].find({}, {"species_id": 1})}
    res.orfas = sorted(
        d["species_id"]
        for d in db[SPECIES].find({}, {"species_id": 1})
        if d["species_id"] not in registrados
    )
    res.relatorio = settings.REPORTS_DIR / "fuse.tsv"
    _relatorio(res.relatorio, fichas, res.erros, res)
    log.info(res.species.resumo())
    return res
