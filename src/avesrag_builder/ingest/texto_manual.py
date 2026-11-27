"""Ingestão dos textos do WikiAves colados à mão: revisao_texto_wikiaves -> raw_texto_manual.

A curadoria cola o texto completo da página de uma ave (plano_texto_manual.md). Esta etapa o
divide nas seções que o `extract` lê (`caracteristicas`, `alimentacao`, `habitos`,
`reproducao`) e grava no envelope das fontes, com o `species_id` como `_id`. O `raw_wikiaves`
não é tocado; na extração, cada campo manual vale por cima do da página coletada.

Trate o texto como dado não confiável: ele só é dividido e guardado.
"""

from __future__ import annotations

import re
from typing import Any

from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.settings import Settings, get_settings
from avesrag_builder.db.collections import (
    RAW_TEXTO_MANUAL,
    RAW_WIKIAVES,
    REVISAO_TEXTO_WIKIAVES,
    SPECIES_REGISTRY,
)
from avesrag_builder.ingest.base import ResultadoIngestao, gravar_envelopes

log = get_logger(__name__)

FONTE = "texto_manual"

# Título (como aparece na página) -> campo. `None` guarda a seção em `outros`.
TITULOS: dict[str, str | None] = {
    "Nome Científico": None,
    "Características": "caracteristicas",
    "Espécies Similares": None,
    "Subespécies": None,
    "Alimentação": "alimentacao",
    "Reprodução": "reproducao",
    "Hábitos": "habitos",
    "Voz": "voz",
    "Distribuição Geográfica": None,
}
CAMPOS = ("caracteristicas", "alimentacao", "habitos", "reproducao")

# Dois jeitos de título: o da página ("Hábitos", que termina a linha: isso exclui
# "Hábitos alimentares…", que abre uma frase, e vale no começo da linha ou grudado no fim do
# texto anterior, "insetoHábitos") e o de wiki ("===== Hábitos =====", com qualquer nome, que
# também delimita as seções que não usamos, como "Ameaças").
_TITULO = re.compile(
    r"={2,}[ \t]*(?P<wiki>[^=\n]{1,40}?)[ \t]*={2,}"
    "|(?P<pagina>" + "|".join(re.escape(t) for t in sorted(TITULOS, key=len, reverse=True)) + r")"
    r"[ \t]*(?:\n|$)"
)


def _limpar(texto: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", texto)).strip()


def dividir(texto: str) -> dict[str, Any]:
    """Texto colado -> `{caracteristicas, alimentacao, habitos, reproducao, outros, titulos}`.

    A seção *Voz* é somada ao `habitos` (o `b02` e o `b03` leem a voz de lá). Seções repetidas
    são juntas na ordem. Sem nenhum título conhecido, devolve `titulos` vazio e o texto todo
    em `outros`: quem chama decide (a espécie não deve ser gravada).
    """
    marcas = list(_TITULO.finditer(texto))
    campos: dict[str, list[str]] = {c: [] for c in (*CAMPOS, "voz")}
    outros: list[str] = []
    ordem: list[str] = []
    antes = _limpar(texto[: marcas[0].start()]) if marcas else _limpar(texto)
    if antes:
        outros.append(antes)
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        corpo = _limpar(texto[m.end() : fim])
        titulo = (m.group("wiki") or m.group("pagina")).strip()
        ordem.append(titulo)
        campo = TITULOS.get(titulo)
        if not corpo:
            continue
        if campo is None:
            outros.append(f"{titulo}: {corpo}")
        else:
            campos[campo].append(corpo)
    voz = " ".join(campos.pop("voz"))
    saida: dict[str, Any] = {c: " ".join(campos[c]) for c in CAMPOS}
    if voz:
        saida["habitos"] = f"{saida['habitos']} {voz}".strip()
    saida["outros"] = "\n".join(outros)
    saida["titulos"] = ordem
    return saida


def _especies_do_registry(db: Database) -> dict[str, str]:
    """species_id -> chave do WikiAves (vazia se a espécie não tem página)."""
    return {
        d["species_id"]: (d.get("chaves") or {}).get("wikiaves") or ""
        for d in db[SPECIES_REGISTRY].find({}, {"species_id": 1, "chaves.wikiaves": 1})
    }


def _paginas(db: Database, chaves: list[str]) -> dict[str, dict[str, Any]]:
    docs = db[RAW_WIKIAVES].find({"_id": {"$in": chaves}}, {"dados.pagina": 1})
    return {d["_id"]: (d.get("dados") or {}).get("pagina") or {} for d in docs}


def _norm(texto: str) -> str:
    return re.sub(r"\W+", " ", texto.lower()).strip()


def ingerir(db: Database, settings: Settings | None = None) -> list[ResultadoIngestao]:
    """Divide e grava os textos colados. Espécie sem título reconhecido ou fora do registry
    não é gravada e vira erro no resultado (nada de chute). Escreve o relatório
    `reports/texto_manual.tsv`: o tamanho de cada seção colada e da página coletada."""
    settings = settings or get_settings()
    chaves = _especies_do_registry(db)
    coletadas = _paginas(db, [c for c in chaves.values() if c])
    registros: list[tuple[str, dict[str, Any]]] = []
    erros: list[str] = []
    linhas = ["species_id\t" + "\t".join(f"{c}_manual\t{c}_coletado" for c in CAMPOS) + "\tmudou"]
    for d in db[REVISAO_TEXTO_WIKIAVES].find().sort("_id", 1):
        sid = d["_id"]
        texto = d.get("texto") or ""
        if sid not in chaves:
            erros.append(f"{sid}: fora do species_registry")
            continue
        partes = dividir(texto)
        if not partes["titulos"] or not any(partes[c] for c in CAMPOS):
            erros.append(f"{sid}: nenhuma seção reconhecida no texto colado")
            continue
        pagina = coletadas.get(chaves[sid], {})
        mudou = any(partes[c] and _norm(partes[c]) != _norm(pagina.get(c) or "") for c in CAMPOS)
        celulas = [x for c in CAMPOS for x in (len(partes[c]), len(pagina.get(c) or ""))]
        linhas.append("\t".join([sid, *map(str, celulas), "sim" if mudou else "não"]))
        registros.append(
            (sid, {**{c: partes[c] for c in CAMPOS}, "outros": partes["outros"], "bruto": texto})
        )
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (settings.REPORTS_DIR / "texto_manual.tsv").write_text("\n".join(linhas) + "\n", "utf-8")
    resultado = gravar_envelopes(db[RAW_TEXTO_MANUAL], registros, FONTE, completo=True)
    resultado.erros.extend(erros)
    return [resultado]
