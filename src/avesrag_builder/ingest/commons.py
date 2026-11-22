"""Wikimedia Commons (imagem P18 do Wikidata) -> raw_commons.

Para cada espécie do escopo (`ingest/escopo.py`), procura no Wikidata o item com
o nome científico (P225) e a sua imagem (P18); depois lê no Commons a licença, o
autor, o crédito e as categorias de cada imagem. Um documento por item:

    _id   = "wikidata:<Q-id>"
    dados = {qid, nomes (P225 que casaram), arquivo, url (miniatura),
             url_original, pagina, licenca, licenca_url, artista, credito
             (HTML, como o Commons devolve), categorias}

Os dados vêm como chegaram: a escolha da foto (licença aceita, se é foto, se o
autor tem nome) é do `fuse`, com `config/regras_midia.yaml`.

Roda depois do `resolve`. ~1 min no piloto: uma consulta SPARQL por bloco de
100 nomes e duas chamadas à API do Commons por bloco de 50 imagens.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import RAW_COMMONS
from avesrag_builder.ingest.base import Registro, ResultadoIngestao, gravar_envelopes
from avesrag_builder.ingest.escopo import especies_com_nomes
from avesrag_builder.ingest.http import ClienteJson

log = get_logger(__name__)

FONTE = "commons"
PREFIXO = "wikidata:"
SPARQL_URL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
BLOCO_NOMES = 100
BLOCO_ARQUIVOS = 50
LARGURA_PX = 640  # o Commons arredonda para um tamanho padrão (960 px em 22/11)
INTERVALO_S = 1.0
CAMPOS_METADATA = {
    "LicenseShortName": "licenca",
    "LicenseUrl": "licenca_url",
    "Artist": "artista",
    "Credit": "credito",
}


def _blocos(itens: list[str], tamanho: int) -> Iterable[list[str]]:
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


# ---------------------------------------------------------------------------
# Wikidata: nome científico -> item e P18
# ---------------------------------------------------------------------------


def consulta_sparql(nomes: list[str]) -> str:
    valores = " ".join('"' + n.replace("\\", "\\\\").replace('"', '\\"') + '"' for n in nomes)
    return (
        f"SELECT ?item ?nome ?img WHERE {{ VALUES ?nome {{ {valores} }} "
        "?item wdt:P225 ?nome . ?item wdt:P18 ?img . }"
    )


def baixar_p18(cliente: ClienteJson, nomes: list[str]) -> list[dict[str, Any]]:
    resposta = cliente.get(SPARQL_URL, {"query": consulta_sparql(nomes), "format": "json"})
    return resposta["results"]["bindings"]


def arquivo_da_url(url: str) -> str:
    """'http://commons.wikimedia.org/wiki/Special:FilePath/Foo%20bar.jpg' -> 'Foo bar.jpg'."""
    return unquote(url.rsplit("/", 1)[-1]).replace("_", " ")


def ler_p18(bindings: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Q-id -> {qid, nomes, arquivo}. Com mais de uma P18, fica a primeira em ordem
    alfabética, para a escolha não mudar de uma execução para outra."""
    itens: dict[str, dict[str, Any]] = {}
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        item = itens.setdefault(qid, {"qid": qid, "nomes": set(), "arquivos": set()})
        item["nomes"].add(b["nome"]["value"])
        item["arquivos"].add(arquivo_da_url(b["img"]["value"]))
    return {
        qid: {"qid": qid, "nomes": sorted(i["nomes"]), "arquivo": min(i["arquivos"])}
        for qid, i in itens.items()
    }


# ---------------------------------------------------------------------------
# Commons: licença, autor e categorias de cada imagem
# ---------------------------------------------------------------------------


def _titulos(arquivos: list[str]) -> str:
    return "|".join(f"File:{a}" for a in arquivos)


def baixar_imageinfo(cliente: ClienteJson, arquivos: list[str]) -> dict[str, Any]:
    return cliente.get(
        COMMONS_API,
        {
            "action": "query",
            "titles": _titulos(arquivos),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": LARGURA_PX,
            "format": "json",
            "formatversion": 2,
        },
    )


def baixar_categorias(cliente: ClienteJson, arquivos: list[str]) -> list[dict[str, Any]]:
    """Todas as páginas da resposta (a lista de categorias vem em partes)."""
    params: dict[str, Any] = {
        "action": "query",
        "titles": _titulos(arquivos),
        "prop": "categories",
        "cllimit": "max",
        "format": "json",
        "formatversion": 2,
    }
    respostas = []
    while True:
        resposta = cliente.get(COMMONS_API, params)
        respostas.append(resposta)
        if "continue" not in resposta:
            return respostas
        params = {**params, **resposta["continue"]}


def sem_rastreamento(url: str | None) -> str | None:
    """Tira os parâmetros `utm_*` que o Commons acrescenta às URLs das imagens."""
    if not url:
        return url
    partes = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(partes.query) if not k.startswith("utm_")]
    return urlunsplit(partes._replace(query=urlencode(query)))


def _por_arquivo(resposta: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    """(arquivo como foi pedido, página) de uma resposta da API do Commons."""
    query = resposta.get("query", {})
    pedido = {n["to"]: n["from"] for n in query.get("normalized", [])}
    for pagina in query.get("pages", []):
        titulo = pedido.get(pagina["title"], pagina["title"])
        yield titulo.removeprefix("File:"), pagina


def ler_imageinfo(resposta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """arquivo -> metadados. Arquivos apagados (sem imageinfo) ficam de fora."""
    out = {}
    for arquivo, pagina in _por_arquivo(resposta):
        if not pagina.get("imageinfo"):
            continue
        info = pagina["imageinfo"][0]
        extmetadata = info.get("extmetadata") or {}
        meta = {
            "url": sem_rastreamento(info.get("thumburl") or info.get("url")),
            "url_original": sem_rastreamento(info.get("url")),
            "pagina": info.get("descriptionurl"),
        }
        for chave, campo in CAMPOS_METADATA.items():
            meta[campo] = (extmetadata.get(chave) or {}).get("value")
        out[arquivo] = meta
    return out


def ler_categorias(respostas: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    categorias: dict[str, set[str]] = {}
    for resposta in respostas:
        for arquivo, pagina in _por_arquivo(resposta):
            conjunto = categorias.setdefault(arquivo, set())
            conjunto.update(c["title"] for c in pagina.get("categories", []))
    return {arquivo: sorted(c) for arquivo, c in categorias.items()}


# ---------------------------------------------------------------------------
# Ingestão
# ---------------------------------------------------------------------------


def montar_registros(
    itens: dict[str, dict[str, Any]],
    metadados: dict[str, dict[str, Any]],
    categorias: dict[str, list[str]],
) -> tuple[list[Registro], list[str]]:
    """Registros dos itens com imagem existente e a lista dos arquivos não achados."""
    registros, sem_arquivo = [], []
    for qid in sorted(itens):
        item = itens[qid]
        meta = metadados.get(item["arquivo"])
        if meta is None:
            sem_arquivo.append(f"{qid}: {item['arquivo']} não existe no Commons")
            continue
        dados = {**item, **meta, "categorias": categorias.get(item["arquivo"], [])}
        registros.append((f"{PREFIXO}{qid}", dados))
    return registros, sem_arquivo


def ingerir(
    db: Database, piloto: bool = False, settings: Settings | None = None
) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    especies = especies_com_nomes(db, piloto, settings.PILOTO_MUNICIPIO_IBGE)
    nomes = sorted({n for e in especies for n in e.nomes})
    cliente = ClienteJson(settings.HTTP_USER_AGENT, intervalo=INTERVALO_S)

    log.info("Wikidata: P18 de %d nomes (%d espécies)…", len(nomes), len(especies))
    bindings: list[dict[str, Any]] = []
    for bloco in _blocos(nomes, BLOCO_NOMES):
        bindings += baixar_p18(cliente, bloco)
    itens = ler_p18(bindings)

    arquivos = sorted({i["arquivo"] for i in itens.values()})
    log.info("Commons: metadados de %d imagens…", len(arquivos))
    metadados: dict[str, dict[str, Any]] = {}
    categorias: dict[str, list[str]] = {}
    for bloco in _blocos(arquivos, BLOCO_ARQUIVOS):
        metadados |= ler_imageinfo(baixar_imageinfo(cliente, bloco))
        categorias |= ler_categorias(baixar_categorias(cliente, bloco))

    registros, sem_arquivo = montar_registros(itens, metadados, categorias)
    resultado = gravar_envelopes(
        db[RAW_COMMONS], registros, FONTE, completo=not piloto, prefixo_completo=PREFIXO
    )
    for aviso in sem_arquivo:  # inconsistência do Wikidata, não da coleta
        log.warning("Commons: %s", aviso)

    nomes_com_p18 = {n for i in itens.values() for n in i["nomes"]}
    com_p18 = sum(1 for e in especies if nomes_com_p18 & set(e.nomes))
    log.info("Commons: %d de %d espécies com imagem P18", com_p18, len(especies))
    return [resultado]
