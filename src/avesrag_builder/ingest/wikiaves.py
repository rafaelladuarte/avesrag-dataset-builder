"""WikiAves -> raw_wikiaves.

Um documento por espécie, com o id do WikiAves (`s=<id>` dos links de mídia):

    dados = {
        "lista":  linha da tabela de especies.php (família, nomes, nº de fotos e sons, URLs),
        "pagina": campos extraídos da página da espécie (textos, classificação, foto…),
    }

1. Baixa a lista completa (uma página) e grava a parte "lista" de todas as
   espécies, mantendo a "pagina" já coletada.
2. Baixa as páginas das espécies escolhidas: todas, ou só as do piloto
   (`--piloto`: espécies com registro no eBird em PILOTO_MUNICIPIO_IBGE).
   Páginas já coletadas são puladas, a menos de `--refazer`; `--limite N`
   para depois de N páginas. Grava a cada 20 páginas, para não perder o
   progresso se o processo cair.

O navegador usa o modo "stealth" e pausas aleatórias entre páginas
(ingest/wikiaves_info.py).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from playwright.sync_api import sync_playwright
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import RAW_AVONET, RAW_BIRDBASE, RAW_EBIRD, RAW_WIKIAVES
from avesrag_builder.ingest.base import Registro, ResultadoIngestao, gravar_envelopes
from avesrag_builder.ingest.wikiaves_especies import URL as URL_LISTA
from avesrag_builder.ingest.wikiaves_especies import extrair_especies
from avesrag_builder.ingest.wikiaves_info import (
    criar_browser_stealth,
    espera_humana,
    extrair_dados_html,
    navegar_com_retry,
)

log = get_logger(__name__)

FONTE = "wikiaves"
BASE_URL = "https://www.wikiaves.com.br"
LOTE_PAGINAS = 20

COLUNAS_NOME_BIRDBASE = (
    "HBW/BirdLife International (v9.1)",
    "IOC World Bird List (v15.1)",
    "AviList v1 2025",
    "Latin (BirdLife > IOC > Clements>AviList)",
)
COLUNA_EBIRD_BIRDBASE = "eBird/Clements (V2024b)"


# ---------------------------------------------------------------------------
# Seleção das espécies do piloto
# ---------------------------------------------------------------------------


def nomes_ebird_do_municipio(db: Database, geocodigo: str) -> list[str]:
    """Nomes científicos (eBird) das espécies registradas no município."""
    municipio = db[RAW_EBIRD].find_one({"_id": f"municipio:{geocodigo}"})
    if not municipio or not municipio["dados"].get("especies"):
        raise ValueError(
            f"raw_ebird não tem a lista do município {geocodigo}: rode `ingest ebird --piloto` antes"
        )
    codigos = municipio["dados"]["especies"]
    taxa = db[RAW_EBIRD].find(
        {"_id": {"$in": [f"taxon:{c}" for c in codigos]}, "dados.category": "species"},
        {"dados.sciName": 1},
    )
    return sorted({t["dados"]["sciName"] for t in taxa})


def ponte_birdbase(db: Database) -> dict[str, set[str]]:
    """Nome eBird/Clements -> nomes da mesma espécie nas outras taxonomias do BIRDBASE."""
    ponte: dict[str, set[str]] = {}
    # Sem projeção por coluna: os nomes têm ponto ("(v9.1)"), que o Mongo lê como subcampo.
    for doc in db[RAW_BIRDBASE].find({}, {"dados": 1}):
        dados = doc["dados"]
        nome_ebird = dados.get(COLUNA_EBIRD_BIRDBASE)
        if not nome_ebird:
            continue
        outros = {dados[c] for c in COLUNAS_NOME_BIRDBASE if dados.get(c)}
        ponte.setdefault(nome_ebird, set()).update(outros)
    return ponte


def ponte_avonet(db: Database) -> dict[str, set[str]]:
    """Nome eBird -> nomes BirdLife, pela tabela de correspondência do AVONET."""
    ponte: dict[str, set[str]] = {}
    for doc in db[RAW_AVONET].find({"_id": {"$regex": "^crosswalk:"}}, {"dados": 1}):
        s1, s2 = doc["dados"].get("Species1"), doc["dados"].get("Species2")
        if s1 and s2:
            ponte.setdefault(s2, set()).add(s1)
    return ponte


def _epiteto(nome: str) -> str:
    return nome.split()[-1]


def selecionar_piloto(
    nomes_ebird: list[str],
    nomes_wikiaves: set[str],
    pontes: list[tuple[str, dict[str, set[str]]]],
) -> tuple[dict[str, str], list[str]]:
    """Escolhe as páginas do WikiAves a baixar para as espécies do eBird.

    Tenta, nesta ordem: nome exato; cada ponte de nomes (BIRDBASE, AVONET);
    mesmo epíteto (gênero trocado, ex.: Chordeiles pusillus -> Nannochordeiles
    pusillus). O epíteto pode trazer páginas a mais (ex.: Chaetura
    meridionalis): é só escopo de coleta, não a definição do piloto, que sai
    do `resolve`.

    Devolve ({nome WikiAves: como casou}, [nomes do eBird sem casamento]).
    """
    por_epiteto: dict[str, set[str]] = {}
    for nome in nomes_wikiaves:
        por_epiteto.setdefault(_epiteto(nome), set()).add(nome)

    escolhidas: dict[str, str] = {}
    sem_casamento: list[str] = []
    for nome in nomes_ebird:
        if nome in nomes_wikiaves:
            escolhidas[nome] = "exato"
            continue
        for rotulo, ponte in pontes:
            candidatos = sorted(ponte.get(nome, set()) & nomes_wikiaves)
            if candidatos:
                for candidato in candidatos:
                    escolhidas.setdefault(candidato, f"{rotulo}:{nome}")
                break
        else:
            candidatos = sorted(por_epiteto.get(_epiteto(nome), set()))
            if candidatos:
                for candidato in candidatos:
                    escolhidas.setdefault(candidato, f"epiteto:{nome}")
            else:
                sem_casamento.append(nome)
    return escolhidas, sem_casamento


# ---------------------------------------------------------------------------
# Montagem dos registros
# ---------------------------------------------------------------------------


def url_pagina(linha: dict) -> str:
    caminho = linha.get("url", "")
    return BASE_URL + (caminho if caminho.startswith("/") else "/" + caminho)


def registro(linha: dict, pagina: dict | None) -> Registro:
    dados: dict[str, Any] = {"lista": linha}
    if pagina is not None:
        dados["pagina"] = pagina
    return linha["id"], dados


def _paginas_existentes(db: Database) -> dict[str, dict]:
    return {
        d["_id"]: d["dados"]["pagina"]
        for d in db[RAW_WIKIAVES].find({"dados.pagina": {"$exists": True}}, {"dados.pagina": 1})
    }


# ---------------------------------------------------------------------------
# Ingestão
# ---------------------------------------------------------------------------


def baixar_lista(page) -> list[dict]:
    html = navegar_com_retry(page, URL_LISTA)
    if html is None:
        raise RuntimeError(f"não foi possível abrir {URL_LISTA}")
    return extrair_especies(html)


def _relatorio_piloto(settings: Settings, sem_casamento: list[str]) -> None:
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = settings.REPORTS_DIR / "wikiaves_piloto_sem_casamento.txt"
    caminho.write_text("".join(f"{n}\n" for n in sem_casamento), encoding="utf-8")
    log.info(f"{len(sem_casamento)} espécies do eBird sem casamento no WikiAves: {caminho}")


def ingerir(
    db: Database,
    piloto: bool = False,
    refazer: bool = False,
    limite: int = 0,
    settings: Settings | None = None,
    progresso: Callable[[int, int, str], None] | None = None,
) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    col = db[RAW_WIKIAVES]

    if piloto:  # falha cedo, antes de abrir o navegador
        nomes_ebird = nomes_ebird_do_municipio(db, settings.PILOTO_MUNICIPIO_IBGE)

    with sync_playwright() as p:
        browser, context = criar_browser_stealth(p)
        page = context.new_page()
        try:
            # 1. Lista
            log.info(f"Baixando a lista de espécies: {URL_LISTA}")
            linhas = baixar_lista(page)
            sem_id = [linha["nome_cientifico"] for linha in linhas if not linha["id"]]
            linhas = [linha for linha in linhas if linha["id"]]
            paginas = _paginas_existentes(db)
            resultado_lista = gravar_envelopes(
                col,
                [registro(linha, paginas.get(linha["id"])) for linha in linhas],
                f"{FONTE} (lista)",
                completo=True,
            )
            resultado_lista.erros.extend(f"sem id na lista: {n}" for n in sem_id)

            # 2. Páginas
            alvo = linhas
            if piloto:
                escolhidas, sem_casamento = selecionar_piloto(
                    nomes_ebird,
                    {linha["nome_cientifico"] for linha in linhas},
                    [("birdbase", ponte_birdbase(db)), ("avonet", ponte_avonet(db))],
                )
                por_tipo: dict[str, int] = {}
                for como in escolhidas.values():
                    tipo = como.split(":")[0]
                    por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
                log.info(
                    f"Piloto: {len(nomes_ebird)} espécies no eBird -> {len(escolhidas)} páginas "
                    f"do WikiAves {por_tipo}"
                )
                _relatorio_piloto(settings, sem_casamento)
                alvo = [linha for linha in linhas if linha["nome_cientifico"] in escolhidas]
            if not refazer:
                alvo = [linha for linha in alvo if linha["id"] not in paginas]
            if limite:
                alvo = alvo[:limite]
            log.info(f"{len(alvo)} páginas a baixar")

            resultado_paginas = ResultadoIngestao(fonte=f"{FONTE} (páginas)", collection=col.name)
            pendentes: list[Registro] = []

            def descarregar() -> None:
                if pendentes:
                    resultado_paginas.somar(
                        gravar_envelopes(col, pendentes, resultado_paginas.fonte)
                    )
                    pendentes.clear()

            for i, linha in enumerate(alvo, start=1):
                url = url_pagina(linha)
                html = navegar_com_retry(page, url)
                if html is None:
                    resultado_paginas.erros.append(
                        f"{linha['id']} {linha['nome_cientifico']}: {url}"
                    )
                else:
                    pagina = extrair_dados_html(html)
                    pagina["url"] = url
                    pendentes.append(registro(linha, pagina))
                if len(pendentes) >= LOTE_PAGINAS:
                    descarregar()
                if i % 10 == 0 or i == len(alvo):
                    log.info(f"{i}/{len(alvo)} páginas ({len(resultado_paginas.erros)} erros)")
                if progresso:
                    progresso(i, len(alvo), linha["nome_cientifico"])
                if i < len(alvo):
                    espera_humana()
            descarregar()
        finally:
            browser.close()

    return [resultado_lista, resultado_paginas]
