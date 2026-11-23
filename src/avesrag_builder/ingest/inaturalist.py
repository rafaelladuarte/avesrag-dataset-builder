"""iNaturalist (fotos de observações "research grade") -> raw_inaturalist.

Para cada espécie do escopo (`ingest/escopo.py`), procura o táxon pelo nome
científico (eBird, depois WikiAves; aceita sinônimo pelo `matched_term`) e
guarda até 5 fotos com licença aberta de observações do Brasil e até 5 de fora.
Um documento por táxon:

    _id   = "taxon:<id do iNaturalist>"
    dados = {taxon: {id, nome, rank}, nomes (do registry, que casaram),
             fotos_brasil[], fotos_mundo[]}
    foto  = {id, url (miniatura `square`, como a API devolve), licenca,
             atribuicao, autor, login, observacao_id, local, data}

Uma foto por observação: a primeira com licença aceita. As licenças vêm de
`config/regras_midia.yaml` e viram o filtro `photo_license` da API. As
observações vêm da API ordenadas pelos votos, e o cliente desempata pelo id; a
contagem de votos não é gravada, porque mudaria o `source_hash` sem a lista
mudar. Limitação (23/11): quase todas têm 0 votos, e a API escolhe as 20 que
devolve com um desempate próprio, que muda com o tempo. Um `--refazer` uma hora
depois trocou as fotos de 56 de 432 táxons. Trocar para `order_by=id` fica
para a expansão (C4 do BACKLOGS). A escolha da foto exibida é do `fuse`.

Roda depois do `resolve`. Três chamadas por espécie a 1 por segundo: ~36 min no
piloto (23/11). As espécies já gravadas são puladas, a menos de `--refazer`; uma
execução interrompida retoma de onde parou.
"""

from __future__ import annotations

from typing import Any

import requests
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.regras_midia import RegrasMidia, regras_midia_padrao
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import RAW_INATURALIST
from avesrag_builder.ingest.base import ResultadoIngestao, gravar_envelopes
from avesrag_builder.ingest.escopo import EspecieEscopo, especies_com_nomes
from avesrag_builder.ingest.http import ClienteJson

log = get_logger(__name__)

FONTE = "inaturalist"
PREFIXO = "taxon:"
API = "https://api.inaturalist.org/v1"
LUGAR_BRASIL = 6878
INTERVALO_S = 1.0  # o iNaturalist pede no máximo ~60 requisições por minuto
POR_PAGINA_TAXA = 100  # o nome procurado pode vir depois de vários nomes populares
POR_PAGINA_OBSERVACOES = 20
FOTOS_POR_LISTA = 5
LOTE_ESPECIES = 20
PROGRESSO_A_CADA = 25


def _normalizar(nome: str | None) -> str:
    return " ".join((nome or "").split()).casefold()


# ---------------------------------------------------------------------------
# Táxon
# ---------------------------------------------------------------------------


def baixar_taxa(cliente: ClienteJson, nome: str) -> dict[str, Any]:
    return cliente.get(
        f"{API}/taxa",
        {"q": nome, "rank": "species", "is_active": "true", "per_page": POR_PAGINA_TAXA},
    )


def escolher_taxon(resposta: dict[str, Any], nome: str) -> dict[str, Any] | None:
    """O táxon cujo nome é `nome` ou, na falta, cujo sinônimo (`matched_term`) é `nome`.

    A busca também casa nomes populares ("Suiriri" traz *Tyrannus melancholicus*);
    por isso só vale a igualdade. Dois táxons diferentes no mesmo critério: nenhum.
    """
    alvo = _normalizar(nome)
    resultados = [r for r in resposta.get("results", []) if r.get("rank") == "species"]
    for campo in ("name", "matched_term"):
        casam = {r["id"]: r for r in resultados if _normalizar(r.get(campo)) == alvo}
        if len(casam) == 1:
            r = next(iter(casam.values()))
            return {"id": r["id"], "nome": r["name"], "rank": r["rank"]}
        if len(casam) > 1:
            log.warning(
                "iNaturalist: %r casa com os táxons %s; nenhum escolhido", nome, sorted(casam)
            )
            return None
    if resposta.get("total_results", 0) > len(resposta.get("results", [])):
        log.warning("iNaturalist: %r não está na primeira página da busca de táxons", nome)
    return None


# ---------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------


def params_observacoes(taxon_id: int, codigos: list[str], brasil: bool) -> dict[str, Any]:
    lugar = "place_id" if brasil else "not_in_place"
    return {
        "taxon_id": taxon_id,
        "quality_grade": "research",
        "photo_license": ",".join(codigos),
        lugar: LUGAR_BRASIL,
        "order_by": "votes",
        "order": "desc",
        "per_page": POR_PAGINA_OBSERVACOES,
    }


def baixar_observacoes(
    cliente: ClienteJson, taxon_id: int, codigos: list[str], brasil: bool
) -> dict[str, Any]:
    return cliente.get(f"{API}/observations", params_observacoes(taxon_id, codigos, brasil))


def ler_fotos(resposta: dict[str, Any], codigos: list[str]) -> list[dict[str, Any]]:
    """Até 5 fotos, uma por observação, das mais votadas (empate: menor id entre as recebidas)."""
    aceitas = {_normalizar(c) for c in codigos}
    observacoes = sorted(
        resposta.get("results", []),
        key=lambda o: (-(o.get("cached_votes_total") or 0), o["id"]),
    )
    fotos = []
    for obs in observacoes:
        foto = next(
            (p for p in obs.get("photos", []) if _normalizar(p.get("license_code")) in aceitas),
            None,
        )
        if foto is None or not foto.get("url"):
            continue
        usuario = obs.get("user") or {}
        fotos.append(
            {
                "id": foto["id"],
                "url": foto["url"],
                "licenca": foto["license_code"],
                "atribuicao": foto.get("attribution"),
                "autor": (usuario.get("name") or "").strip() or None,
                "login": usuario.get("login"),
                "observacao_id": obs["id"],
                "local": obs.get("place_guess"),
                "data": obs.get("observed_on"),
            }
        )
        if len(fotos) == FOTOS_POR_LISTA:
            break
    return fotos


# ---------------------------------------------------------------------------
# Ingestão
# ---------------------------------------------------------------------------


class _Coleta:
    """Estado de uma execução: registros a gravar e os já conhecidos, por `_id`."""

    def __init__(self, db: Database, refazer: bool):
        self.col = db[RAW_INATURALIST]
        self.resultado = ResultadoIngestao(fonte=FONTE, collection=self.col.name)
        # Gravados antes: dão a retomada e evitam buscar de novo as fotos de um
        # táxon que uma segunda espécie também usa. Com --refazer, tudo é buscado.
        self.gravados: dict[str, dict[str, Any]] = (
            {}
            if refazer
            else {d["_id"]: d["dados"] for d in self.col.find({"_id": {"$regex": f"^{PREFIXO}"}})}
        )
        self.nesta_execucao: dict[str, dict[str, Any]] = {}
        self.pendentes: dict[str, dict[str, Any]] = {}

    def nomes_gravados(self) -> set[str]:
        return {_normalizar(n) for dados in self.gravados.values() for n in dados.get("nomes", [])}

    def conhecido(self, id_: str) -> dict[str, Any] | None:
        return self.nesta_execucao.get(id_) or self.gravados.get(id_)

    def guardar(self, id_: str, dados: dict[str, Any]) -> None:
        self.nesta_execucao[id_] = dados
        self.pendentes[id_] = dados

    def descarregar(self) -> None:
        if self.pendentes:
            registros = sorted(self.pendentes.items())
            self.resultado.somar(gravar_envelopes(self.col, registros, FONTE))
            self.pendentes.clear()


def _buscar_taxon(
    cliente: ClienteJson, especie: EspecieEscopo
) -> tuple[dict[str, Any], str] | None:
    for nome in especie.nomes:
        taxon = escolher_taxon(baixar_taxa(cliente, nome), nome)
        if taxon:
            return taxon, nome
    return None


def _coletar_especie(
    cliente: ClienteJson, coleta: _Coleta, especie: EspecieEscopo, codigos: list[str]
) -> bool:
    """Busca e guarda uma espécie. False se o iNaturalist não tem o táxon."""
    achado = _buscar_taxon(cliente, especie)
    if achado is None:
        return False
    taxon, nome = achado
    id_ = f"{PREFIXO}{taxon['id']}"
    existente = coleta.conhecido(id_)
    if existente is not None:  # outra espécie do registry no mesmo táxon
        nomes = sorted(set(existente["nomes"]) | {nome})
        if nomes != existente["nomes"]:
            coleta.guardar(id_, {**existente, "nomes": nomes})
        return True
    coleta.guardar(
        id_,
        {
            "taxon": taxon,
            "nomes": [nome],
            "fotos_brasil": ler_fotos(
                baixar_observacoes(cliente, taxon["id"], codigos, True), codigos
            ),
            "fotos_mundo": ler_fotos(
                baixar_observacoes(cliente, taxon["id"], codigos, False), codigos
            ),
        },
    )
    return True


def ingerir(
    db: Database,
    piloto: bool = False,
    refazer: bool = False,
    settings: Settings | None = None,
    regras: RegrasMidia | None = None,
    cliente: ClienteJson | None = None,
) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    codigos = (regras or regras_midia_padrao()).codigos_inaturalist()
    cliente = cliente or ClienteJson(settings.HTTP_USER_AGENT, intervalo=INTERVALO_S)
    especies = especies_com_nomes(db, piloto, settings.PILOTO_MUNICIPIO_IBGE)
    coleta = _Coleta(db, refazer)

    ja_gravados = coleta.nomes_gravados()
    pendentes = [e for e in especies if not ja_gravados & {_normalizar(n) for n in e.nomes}]
    log.info(
        "iNaturalist: %d espécies no escopo, %d já gravadas, %d a buscar (licenças: %s)",
        len(especies),
        len(especies) - len(pendentes),
        len(pendentes),
        ",".join(codigos),
    )

    sem_taxon: list[EspecieEscopo] = []
    for i, especie in enumerate(pendentes, start=1):
        try:
            if not _coletar_especie(cliente, coleta, especie, codigos):
                sem_taxon.append(especie)
        except requests.RequestException as e:
            # Não grava: uma falha não pode virar "lista vazia". A próxima execução tenta de novo.
            coleta.resultado.erros.append(f"{especie.species_id}: {e}")
        if i % LOTE_ESPECIES == 0:
            coleta.descarregar()
        if i % PROGRESSO_A_CADA == 0:
            log.info("iNaturalist: %d de %d espécies", i, len(pendentes))
    coleta.descarregar()

    if refazer and not piloto:
        coleta.resultado.ausentes_na_fonte = coleta.col.count_documents(
            {"_id": {"$regex": f"^{PREFIXO}", "$nin": list(coleta.nesta_execucao)}}
        )
    for especie in sem_taxon:
        log.warning(
            "iNaturalist: sem táxon para %s (%s)", especie.species_id, ", ".join(especie.nomes)
        )
    _resumir(coleta, especies)
    return [coleta.resultado]


def _resumir(coleta: _Coleta, especies: list[EspecieEscopo]) -> None:
    registros = {**coleta.gravados, **coleta.nesta_execucao}
    por_nome = {_normalizar(n): dados for dados in registros.values() for n in dados["nomes"]}
    com_taxon = brasil = so_mundo = 0
    for especie in especies:
        dados = next((por_nome[n] for n in map(_normalizar, especie.nomes) if n in por_nome), None)
        if dados is None:
            continue
        com_taxon += 1
        if dados["fotos_brasil"]:
            brasil += 1
        elif dados["fotos_mundo"]:
            so_mundo += 1
    log.info(
        "iNaturalist: %d de %d espécies com táxon; %d com foto do Brasil, %d só com foto de fora",
        com_taxon,
        len(especies),
        brasil,
        so_mundo,
    )
