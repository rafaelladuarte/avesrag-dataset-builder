"""Validações e classificação de uma ficha de `species` (Especificação > Data quality).

Funções puras sobre o documento como está no Mongo. Uma ficha que falha numa
validação fica `bloqueada`; uma que passa em todas fica `apta` se tiver o mínimo
de `config/regras_fusao.yaml` (`apta.minimos` e `apta.textos_b03`), senão
`incompleta`.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from avesrag_builder.core.models import DqStatus, Species
from avesrag_builder.core.regras_fusao import RegrasFusao
from avesrag_builder.core.vocabulario import Vocabulario

# Campos fora de `atributos` que precisam de `_prov` quando preenchidos.
CAMPOS_TOPO = (
    "nomes.pt",
    "nomes.en",
    "taxonomia",
    "status_ocorrencia",
    "iucn",
    "ocorrencia",
    "midia",
)
NIVEIS_TAXONOMIA = ("ordem", "familia", "genero")
# Partes de `midia` com `_prov` próprio.
MIDIA_COM_PROV = ("foto", "fotos", "ilustracao")


def _valor(doc: dict[str, Any], caminho: str) -> Any:
    atual: Any = doc
    for parte in caminho.split("."):
        if not isinstance(atual, dict):
            return None
        atual = atual.get(parte)
    return atual


def _preenchido(valor: Any) -> bool:
    return valor not in (None, "", [], {})


def campos_preenchidos(doc: dict[str, Any]) -> set[str]:
    caminhos = {c for c in CAMPOS_TOPO if c != "midia" and _preenchido(_valor(doc, c))}
    # `midia` (link do WikiAves), `midia.foto` (iNaturalist ou Commons) e
    # `midia.ilustracao` (Bird Album) têm proveniências separadas.
    midia = doc.get("midia") or {}
    if any(_preenchido(v) for k, v in midia.items() if k not in MIDIA_COM_PROV):
        caminhos.add("midia")
    for chave in MIDIA_COM_PROV:
        if _preenchido(midia.get(chave)):
            caminhos.add(f"midia.{chave}")
    for nome, valor in (doc.get("atributos") or {}).items():
        if _preenchido(valor):
            caminhos.add(f"atributos.{nome}")
    for nome, valor in (doc.get("perfil") or {}).items():
        if _preenchido(valor):
            caminhos.add(f"perfil.{nome}")
    return caminhos


def _categoricos(doc: dict[str, Any], vocab: Vocabulario) -> list[str]:
    erros = []
    atributos = doc.get("atributos") or {}
    for nome, valor in atributos.items():
        if nome in ("comprimento_cm", "cores_por_parte") or valor is None:
            continue
        if nome not in vocab.atributos:
            erros.append(f"atributos.{nome}: atributo fora do vocabulário")
            continue
        for v in valor if isinstance(valor, list) else [valor]:
            if not vocab.contem(nome, v):
                erros.append(f"atributos.{nome}: {v!r} não está no vocabulário")
    partes = set(vocab.partes())
    cor = vocab.arquivo.cores_por_parte.cor
    for item in atributos.get("cores_por_parte") or []:
        if item.get("parte") not in partes:
            erros.append(
                f"atributos.cores_por_parte: parte {item.get('parte')!r} fora do vocabulário"
            )
        if not vocab.contem(cor, item.get("cor") or ""):
            erros.append(f"atributos.cores_por_parte: cor {item.get('cor')!r} fora do vocabulário")
    iucn = doc.get("iucn")
    if iucn is not None and not vocab.contem("iucn", iucn):
        erros.append(f"iucn: {iucn!r} não está no vocabulário")
    return erros


def erros(
    doc: dict[str, Any],
    vocab: Vocabulario,
    regras: RegrasFusao,
    registrados: set[str],
) -> list[str]:
    """As 6 validações; lista vazia = passou em todas."""
    out: list[str] = []

    # 1. Valores categóricos no vocabulário.
    out += _categoricos(doc, vocab)

    # 2. Comprimento plausível.
    comp = _valor(doc, "atributos.comprimento_cm")
    if comp is not None and not regras.comprimento_valido(comp):
        lim = regras.arquivo.comprimento_cm
        out.append(f"atributos.comprimento_cm: {comp} fora de {lim.min:g}–{lim.max:g} cm")

    # 3. _prov coerente com os campos.
    prov = doc.get("_prov") or {}
    preenchidos = campos_preenchidos(doc)
    for campo in sorted(preenchidos - set(prov)):
        out.append(f"_prov: falta a entrada de {campo}")
    for campo in sorted(set(prov) - preenchidos):
        out.append(f"_prov.{campo}: aponta para um campo vazio ou inexistente")

    # 4. Nenhum campo vazio (o modelo rejeita "", lista vazia; null não é gravado).
    try:
        Species.from_mongo(doc)
    except ValidationError as e:
        for err in e.errors():
            local = ".".join(str(p) for p in err["loc"]) or "documento"
            out.append(f"{local}: {err['msg']}")

    # 5. Taxonomia completa e de uma única fonte.
    tax = doc.get("taxonomia") or {}
    faltando = [n for n in NIVEIS_TAXONOMIA if not tax.get(n)]
    if faltando:
        out.append(f"taxonomia: falta {', '.join(faltando)}")
    fonte_tax = (prov.get("taxonomia") or {}).get("fonte", "")
    if "+" in fonte_tax:
        out.append(f"taxonomia: mais de uma fonte ({fonte_tax})")

    # 6. Mesmo species_id do registry (a unicidade é conferida no conjunto).
    if doc.get("species_id") not in registrados:
        out.append(f"species_id: {doc.get('species_id')!r} não está no registry")

    return out


def faltas(doc: dict[str, Any], regras: RegrasFusao, textos_b03: set[str]) -> list[str]:
    """O que falta para a ficha ser `apta` (lista vazia = apta)."""
    out = []
    atributos = doc.get("atributos") or {}
    for nome, minimo in regras.minimos.items():
        valor = atributos.get(nome)
        qtd = len(valor) if isinstance(valor, list) else int(_preenchido(valor))
        if qtd < minimo:
            out.append(f"{nome} ({qtd} de {minimo})" if minimo > 1 else nome)
    for texto in regras.textos_b03:
        if texto not in textos_b03:
            out.append(f"b03.{texto}")
    return out


def classificar(erros_: list[str], faltas_: list[str]) -> DqStatus:
    if erros_:
        return "bloqueada"
    return "incompleta" if faltas_ else "apta"
