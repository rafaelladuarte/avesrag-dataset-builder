"""Documentos de busca esperados para uma ficha e o plano de gravação (funções puras).

Cada espécie `apta` tem até três documentos, um por domínio do `b03` com texto.
O texto é o do `b03`, sem o nome da espécie (os nomes vão num campo à parte, só
para o `$search`). Os filtros são copiados da ficha e são iguais nos três
documentos, porque o `$vectorSearch` só pré-filtra pelo próprio documento.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from avesrag_builder.core.models import Atributos

DOMINIOS = ("aparencia", "comportamento_ambiente", "voz_habitos")

# Atributos da ficha que não viram filtro: o número e a lista de pares (parte, cor),
# que o índice não consegue filtrar como valor simples.
FORA_DOS_FILTROS = ("comprimento_cm", "cores_por_parte")
CHAVES_FILTRO = (
    *(nome for nome in Atributos.model_fields if nome not in FORA_DOS_FILTROS),
    "familia",
    "biomas",
)

Status = Literal["novo", "alterado", "so_filtros", "inalterado", "removido"]


@dataclass(frozen=True)
class DocEsperado:
    species_id: str
    dominio: str
    texto: str
    nomes: list[str]
    filtros: dict[str, Any]

    @property
    def id(self) -> str:
        return f"{self.species_id}:{self.dominio}"


def filtros(ficha: dict[str, Any]) -> dict[str, Any]:
    atributos = ficha.get("atributos") or {}
    out = {k: atributos[k] for k in CHAVES_FILTRO if atributos.get(k)}
    familia = (ficha.get("taxonomia") or {}).get("familia")
    if familia:
        out["familia"] = familia
    biomas = (ficha.get("ocorrencia") or {}).get("biomas")
    if biomas:
        out["biomas"] = list(biomas)
    return out


def nomes(ficha: dict[str, Any]) -> list[str]:
    """Nomes em português, o científico e os em inglês, sem repetição."""
    n = ficha.get("nomes") or {}
    todos = [*(n.get("pt") or []), ficha.get("nome_cientifico"), *(n.get("en") or [])]
    return list(dict.fromkeys(t.strip() for t in todos if t and t.strip()))


def esperados(ficha: dict[str, Any], b03: dict[str, Any] | None) -> list[DocEsperado]:
    """Documentos de uma ficha apta; domínio sem texto no b03 não gera documento."""
    if not b03 or not (b03.get("validacao") or {}).get("ok"):
        return []
    saida = b03.get("saida") or {}
    base = {"species_id": ficha["species_id"], "nomes": nomes(ficha), "filtros": filtros(ficha)}
    return [
        DocEsperado(dominio=dominio, texto=saida[dominio].strip(), **base)
        for dominio in DOMINIOS
        if (saida.get(dominio) or "").strip()
    ]


@dataclass
class Plano:
    """O que fazer com cada documento: quais precisam de embedding e quais saem."""

    status: dict[str, Status] = field(default_factory=dict)
    gerar: list[DocEsperado] = field(default_factory=list)  # novo ou alterado
    reaproveitar: list[DocEsperado] = field(default_factory=list)  # só filtros/nomes mudaram
    remover: list[str] = field(default_factory=list)


def planejar(
    docs: Iterable[DocEsperado], existentes: dict[str, dict[str, Any]], modelo: str
) -> Plano:
    """Compara com os documentos gravados (`_id` -> doc) das espécies do escopo.

    O embedding é reaproveitado quando o texto e o modelo são os mesmos; os
    documentos gravados que não são mais esperados saem.
    """
    plano = Plano()
    ids = set()
    for doc in docs:
        ids.add(doc.id)
        atual = existentes.get(doc.id)
        if atual is None:
            plano.status[doc.id] = "novo"
            plano.gerar.append(doc)
        elif atual.get("texto") != doc.texto or atual.get("modelo") != modelo:
            plano.status[doc.id] = "alterado"
            plano.gerar.append(doc)
        elif atual.get("nomes") != doc.nomes or atual.get("filtros") != doc.filtros:
            plano.status[doc.id] = "so_filtros"
            plano.reaproveitar.append(doc)
        else:
            plano.status[doc.id] = "inalterado"
    for _id in sorted(set(existentes) - ids):
        plano.status[_id] = "removido"
        plano.remover.append(_id)
    return plano
