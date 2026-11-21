"""Contratos de saída dos prompts b01–b03, gerados do `vocabulario.yaml`.

Cada atributo vira uma chave com uma lista de `{valor, evidencia}` (em
`cores_por_parte`, `{parte, cor, evidencia}`) ou `null`. Os valores são `Literal`
do vocabulário, então o JSON Schema estrito enviado ao LLM já os traz como
`enum` e a validação Pydantic confere de novo (Modelo de Dados > Contratos do builder).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from avesrag_builder.core.models import TextoNaoVazio
from avesrag_builder.core.vocabulario import ATRIBUTO_CORES_POR_PARTE, Vocabulario

DOMINIOS_B03 = ("aparencia", "comportamento_ambiente", "voz_habitos")
# O prompt pede até ~600 caracteres; a validação tolera um pouco mais.
LIMITE_TEXTO_B03 = 700
# Palavras-chave de JSON Schema que o modo estrito não aceita ou que não interessam
# ao modelo (a validação Pydantic cuida delas depois).
_CHAVES_FORA_DO_ESTRITO = {"default", "minLength", "maxLength", "minItems", "maxItems", "title"}


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Comprimento(_Base):
    min: float = Field(gt=0)
    max: float = Field(gt=0)
    evidencia: TextoNaoVazio

    @model_validator(mode="after")
    def _ordem(self) -> Comprimento:
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) maior que max ({self.max})")
        return self


def _literal(valores: list[str]) -> Any:
    return Literal[tuple(valores)]  # type: ignore[valid-type]


def _nome_classe(atributo: str) -> str:
    return "Item" + "".join(p.capitalize() for p in atributo.split("_"))


def _modelo_item(atributo: str, voc: Vocabulario) -> type[BaseModel]:
    if atributo == ATRIBUTO_CORES_POR_PARTE:
        campos: dict[str, Any] = {
            "parte": (_literal(voc.partes()), ...),
            "cor": (_literal(voc.valores(voc.arquivo.cores_por_parte.cor)), ...),
        }
    else:
        campos = {"valor": (_literal(voc.valores(atributo)), ...)}
    # O valor vem antes da evidência: é a ordem em que o modelo escreve.
    campos["evidencia"] = (TextoNaoVazio, ...)
    return create_model(_nome_classe(atributo), __base__=_Base, **campos)


def _sem_listas_vazias(self: BaseModel) -> BaseModel:
    for nome in type(self).model_fields:
        if getattr(self, nome) == []:
            raise ValueError(f"{nome}: lista vazia (use null)")
    return self


def contrato_atributos(
    nome: str, atributos: list[str], voc: Vocabulario, comprimento: bool
) -> type[BaseModel]:
    campos: dict[str, Any] = {}
    if comprimento:
        campos["comprimento_cm"] = (Comprimento | None, ...)
    for atributo in atributos:
        campos[atributo] = (list[_modelo_item(atributo, voc)] | None, ...)
    return create_model(
        nome,
        __base__=_Base,
        __validators__={"_sem_listas_vazias": model_validator(mode="after")(_sem_listas_vazias)},
        **campos,
    )


class B03TextosBusca(_Base):
    aparencia: str | None
    comportamento_ambiente: str | None
    voz_habitos: str | None

    @model_validator(mode="after")
    def _textos(self) -> B03TextosBusca:
        for dominio in DOMINIOS_B03:
            texto = getattr(self, dominio)
            if texto is not None and not texto.strip():
                raise ValueError(f"{dominio}: texto vazio (use null)")
            if texto is not None and len(texto) > LIMITE_TEXTO_B03:
                raise ValueError(f"{dominio}: {len(texto)} caracteres (limite {LIMITE_TEXTO_B03})")
        return self


# Nome do schema no YAML do prompt -> construtor do contrato (atributos do prompt, vocabulário).
CONSTRUTORES: dict[str, Callable[[list[str], Vocabulario], type[BaseModel]]] = {
    "B01Aparencia": lambda attrs, voc: contrato_atributos("B01Aparencia", attrs, voc, True),
    "B02Comportamento": lambda attrs, voc: contrato_atributos(
        "B02Comportamento", attrs, voc, False
    ),
    "B03TextosBusca": lambda attrs, voc: B03TextosBusca,
}
SCHEMAS = set(CONSTRUTORES)


def contrato(schema_nome: str, atributos: list[str], voc: Vocabulario) -> type[BaseModel]:
    return CONSTRUTORES[schema_nome](atributos, voc)


# ---------------------------------------------------------------------------
# JSON Schema estrito
# ---------------------------------------------------------------------------


def _estrito(no: Any) -> Any:
    if isinstance(no, list):
        return [_estrito(x) for x in no]
    if not isinstance(no, dict):
        return no
    novo = {k: _estrito(v) for k, v in no.items() if k not in _CHAVES_FORA_DO_ESTRITO}
    if "properties" in no:
        # O modo estrito exige todos os campos em `required` e nada além deles.
        novo["properties"] = {k: _estrito(v) for k, v in no["properties"].items()}
        novo["required"] = list(no["properties"])
        novo["additionalProperties"] = False
    return novo


def schema_estrito(modelo: type[BaseModel]) -> dict[str, Any]:
    """`{"name", "strict", "schema"}` no formato `json_schema` da OpenAI."""
    schema = copy.deepcopy(modelo.model_json_schema())
    return {"name": modelo.__name__, "strict": True, "schema": _estrito(schema)}


# ---------------------------------------------------------------------------
# Normalização da saída
# ---------------------------------------------------------------------------


def _chave_item(item: Any) -> Any:
    if isinstance(item, dict):
        return tuple(sorted((k, v) for k, v in item.items() if k != "evidencia"))
    return item


def normalizar_saida(saida: dict[str, Any]) -> dict[str, Any]:
    """Tira valores repetidos no mesmo campo (fica a primeira evidência) e troca
    lista ou texto vazio por null. O modelo às vezes ignora essas regras do prompt.
    """
    normal: dict[str, Any] = {}
    for campo, valor in saida.items():
        if isinstance(valor, list):
            vistos: set[Any] = set()
            itens = []
            for item in valor:
                chave = _chave_item(item)
                if chave not in vistos:
                    vistos.add(chave)
                    itens.append(item)
            valor = itens or None
        elif isinstance(valor, str) and not valor.strip():
            valor = None
        normal[campo] = valor
    return normal
