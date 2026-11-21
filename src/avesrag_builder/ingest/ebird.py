"""eBird -> raw_ebird.

Dois tipos de documento, separados pelo prefixo do `_id`:

- `taxon:<speciesCode>`: a taxonomia completa do eBird (`/ref/taxonomy/ebird`,
  nomes comuns em pt_BR), como a API devolve. É a ponte para o `speciesCode`
  usada pela etapa `resolve`.
- `municipio:<geocódigo IBGE>`: a região do eBird casada com o município do
  IBGE (nome exato ou fuzzy) e a lista de espécies já registradas nela
  (`/product/spplist/<região>`), como a API devolve.

Com `--piloto`, só o município de PILOTO_MUNICIPIO_IBGE (3 chamadas à API).
Sem ele, todos os 5.572 municípios (cerca de 1 a 2 horas); os já gravados
são pulados, a menos que `--refazer` seja usado.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests
from pymongo.database import Database
from rapidfuzz import fuzz, process

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.core.texto import normalizar_termo
from avesrag_builder.db.collections import RAW_EBIRD
from avesrag_builder.ingest import ibge
from avesrag_builder.ingest.base import Registro, ResultadoIngestao, gravar_envelopes

log = get_logger(__name__)

FONTE = "ebird"
BASE_URL = "https://api.ebird.org/v2"
LOCALE = "pt_BR"
PAUSA_ENTRE_CHAMADAS_S = 0.6
FUZZY_MINIMO = 85
LOTE_MUNICIPIOS = 100

PREFIXO_TAXON = "taxon:"
PREFIXO_MUNICIPIO = "municipio:"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def ebird_get(path: str, params: dict | None = None) -> Any:
    """GET autenticado na API do eBird, com retry e backoff no 429."""
    key = get_settings().EBIRD_API_KEY
    headers = {"X-eBirdApiToken": key.get_secret_value() if key else ""}
    url = f"{BASE_URL}{path}"
    for tentativa in range(4):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=60)
            if r.status_code == 429:
                espera = 10 * (2**tentativa)
                log.warning(
                    f"Rate limit em {path}; aguardando {espera}s (tentativa {tentativa + 1})"
                )
                time.sleep(espera)
                continue
            r.raise_for_status()
            return r.json()
        except requests.HTTPError:
            raise
        except requests.RequestException as e:
            log.warning(f"Erro de rede em {path}: {e} (tentativa {tentativa + 1}/4)")
            time.sleep(3)
    raise RuntimeError(f"falha ao acessar {path} após 4 tentativas")


def baixar_taxonomia() -> list[dict]:
    return ebird_get("/ref/taxonomy/ebird", params={"fmt": "json", "locale": LOCALE})


def baixar_regioes(uf: str) -> list[dict]:
    """Municípios (subnational2) do eBird numa UF: [{code, name}]."""
    regioes = ebird_get(f"/ref/region/list/subnational2/BR-{uf}")
    time.sleep(PAUSA_ENTRE_CHAMADAS_S)
    return regioes


def baixar_especies(codigo_regiao: str) -> list[str]:
    """speciesCodes já registrados na região, na ordem da API."""
    codigos = ebird_get(f"/product/spplist/{codigo_regiao}")
    time.sleep(PAUSA_ENTRE_CHAMADAS_S)
    return codigos


# ---------------------------------------------------------------------------
# Casamento IBGE <-> eBird
# ---------------------------------------------------------------------------


def casar_municipio(municipio: dict, regioes: list[dict]) -> dict:
    """Casa um município do IBGE com uma região do eBird da mesma UF.

    Nome normalizado exato (sem acento, caixa, apóstrofo e hífen); senão, fuzzy
    (token_sort_ratio >= 85).
    Devolve {ebird_code, ebird_name, match_type}; sem casamento, code None.
    """
    por_nome = {normalizar_termo(r["name"]): r for r in regioes}
    nome = normalizar_termo(municipio["nome"])
    if nome in por_nome:
        r = por_nome[nome]
        return {"ebird_code": r["code"], "ebird_name": r["name"], "match_type": "exato"}
    melhor = process.extractOne(nome, list(por_nome), scorer=fuzz.token_sort_ratio)
    if melhor and melhor[1] >= FUZZY_MINIMO:
        r = por_nome[melhor[0]]
        return {
            "ebird_code": r["code"],
            "ebird_name": r["name"],
            "match_type": f"fuzzy:{round(melhor[1])}",
        }
    return {"ebird_code": None, "ebird_name": None, "match_type": "sem_match"}


def municipios_ibge(settings: Settings) -> list[dict]:
    """[{geocodigo, nome, uf}] da planilha do IBGE."""
    return [
        {
            "geocodigo": id_,
            "nome": dados["Nome do município"],
            "uf": dados["Sigla da UF"],
        }
        for id_, dados in ibge.ler(settings.IBGE_XLSX)
    ]


# ---------------------------------------------------------------------------
# Ingestão
# ---------------------------------------------------------------------------


# A API devolve estas listas em ordem diferente a cada chamada; o conteúdo é
# um conjunto de códigos. Ordenar evita que o source_hash mude sem mudança real.
LISTAS_SEM_ORDEM = ("bandingCodes", "comNameCodes", "sciNameCodes")


def registros_taxonomia(taxa: list[dict]) -> list[Registro]:
    registros = []
    for t in taxa:
        dados = dict(t)
        for campo in LISTAS_SEM_ORDEM:
            if isinstance(dados.get(campo), list):
                dados[campo] = sorted(dados[campo])
        registros.append((f"{PREFIXO_TAXON}{t['speciesCode']}", dados))
    return registros


def registro_municipio(municipio: dict, casamento: dict, especies: list[str] | None) -> Registro:
    dados = {**municipio, **casamento, "especies": especies}
    return f"{PREFIXO_MUNICIPIO}{municipio['geocodigo']}", dados


def _salvar_sem_match(settings: Settings, sem_match: list[dict]) -> None:
    if not sem_match:
        return
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = settings.REPORTS_DIR / "ebird_municipios_sem_match.tsv"
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("geocodigo\tnome\tuf\n")
        for m in sem_match:
            f.write(f"{m['geocodigo']}\t{m['nome']}\t{m['uf']}\n")
    log.info(f"{len(sem_match)} municípios sem região no eBird: {caminho}")


def ingerir(
    db: Database,
    piloto: bool = False,
    refazer: bool = False,
    settings: Settings | None = None,
    progresso: Callable[[int, int], None] | None = None,
) -> list[ResultadoIngestao]:
    settings = settings or get_settings()
    settings.require("EBIRD_API_KEY")
    col = db[RAW_EBIRD]

    # 1. Taxonomia (uma chamada)
    log.info("Baixando a taxonomia do eBird…")
    taxonomia = gravar_envelopes(
        col,
        registros_taxonomia(baixar_taxonomia()),
        f"{FONTE} (taxonomia)",
        completo=True,
        prefixo_completo=PREFIXO_TAXON,
    )

    # 2. Municípios
    municipios = municipios_ibge(settings)
    if piloto:
        municipios = [m for m in municipios if m["geocodigo"] == settings.PILOTO_MUNICIPIO_IBGE]
        if not municipios:
            raise ValueError(
                f"PILOTO_MUNICIPIO_IBGE={settings.PILOTO_MUNICIPIO_IBGE} não está no IBGE"
            )
    elif not refazer:
        ja_gravados = {
            d["_id"].removeprefix(PREFIXO_MUNICIPIO)
            for d in col.find({"_id": {"$regex": f"^{PREFIXO_MUNICIPIO}"}}, {"_id": 1})
        }
        municipios = [m for m in municipios if m["geocodigo"] not in ja_gravados]
        log.info(f"{len(ja_gravados)} municípios já gravados; {len(municipios)} pendentes")

    resultado = ResultadoIngestao(fonte=f"{FONTE} (municípios)", collection=col.name)
    regioes_por_uf: dict[str, list[dict]] = {}
    sem_match: list[dict] = []
    pendentes: list[Registro] = []

    def descarregar() -> None:
        if pendentes:
            resultado.somar(gravar_envelopes(col, pendentes, resultado.fonte))
            pendentes.clear()

    for i, municipio in enumerate(municipios, start=1):
        uf = municipio["uf"]
        if uf not in regioes_por_uf:
            try:
                regioes_por_uf[uf] = baixar_regioes(uf)
            except (requests.HTTPError, RuntimeError) as e:
                regioes_por_uf[uf] = []
                resultado.erros.append(f"regiões de {uf}: {e}")
        casamento = casar_municipio(municipio, regioes_por_uf[uf])
        especies = None
        if casamento["ebird_code"]:
            try:
                especies = baixar_especies(casamento["ebird_code"])
            except (requests.HTTPError, RuntimeError) as e:
                resultado.erros.append(f"{municipio['geocodigo']} ({casamento['ebird_code']}): {e}")
                continue  # não grava: uma falha não pode virar "lista vazia"
        else:
            sem_match.append(municipio)
        pendentes.append(registro_municipio(municipio, casamento, especies))
        if len(pendentes) >= LOTE_MUNICIPIOS:
            descarregar()
        if progresso:
            progresso(i, len(municipios))
    descarregar()

    if not piloto:
        _salvar_sem_match(settings, sem_match)
    return [taxonomia, resultado]
