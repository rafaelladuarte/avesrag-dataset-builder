"""Leitor validado dos prompts do builder (`config/prompts/*.yaml`).

Um YAML por prompt (Modelo de Dados > Prompts e contratos JSON). O bloco de
valores permitidos é injetado do `vocabulario.yaml` em `{vocabulario}`; os
textos do WikiAves listados em `campos` entram em `entrada`.
"""

from __future__ import annotations

import string
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from avesrag_builder.core.vocabulario import (
    ATRIBUTO_CORES_POR_PARTE,
    Vocabulario,
    VocabularioInvalido,
    _erros_pydantic,
    _ler_yaml,
)

# Textos da página do WikiAves (`raw_wikiaves.dados.pagina`) que um prompt pode usar.
CAMPOS_WIKIAVES = ("caracteristicas", "alimentacao", "habitos", "reproducao")
PROMPTS_DO_BUILDER = ("b01_aparencia", "b02_comportamento", "b03_textos_busca")


class PromptInvalido(VocabularioInvalido):
    """Arquivo de prompt com erro; a mensagem aponta o caminho."""


def _placeholders(texto: str) -> set[str]:
    return {nome for _, nome, _, _ in string.Formatter().parse(texto) if nome is not None}


class Prompt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    versao: str
    modelo: str | None = None  # sem modelo, vale o LLM_MODEL do settings
    temperatura: float | None = None  # null: o parâmetro não é enviado
    schema_: str = Field(alias="schema")
    vocabulario: list[str]
    campos: list[str] = Field(min_length=1)
    system: str
    entrada: str

    @property
    def schema_nome(self) -> str:
        return self.schema_

    def render_system(self, vocabulario: Vocabulario) -> str:
        if not self.vocabulario:
            return self.system.strip()
        return self.system.format(vocabulario=vocabulario.para_prompt(self.vocabulario)).strip()

    def render_entrada(self, textos: dict[str, str]) -> str:
        return self.entrada.format(**{c: textos.get(c, "") for c in self.campos}).strip()


def _erros_de_conteudo(p: Prompt, vocabulario: Vocabulario, schemas: set[str]) -> list[str]:
    erros = []
    if p.schema_nome not in schemas:
        erros.append(f"schema: {p.schema_nome!r} não existe ({', '.join(sorted(schemas))})")
    conhecidos = {*vocabulario.atributos, ATRIBUTO_CORES_POR_PARTE}
    for nome in p.vocabulario:
        if nome not in conhecidos:
            erros.append(f"vocabulario: atributo {nome!r} não existe no vocabulario.yaml")
    for campo in p.campos:
        if campo not in CAMPOS_WIKIAVES:
            erros.append(
                f"campos: {campo!r} não é um texto do WikiAves ({', '.join(CAMPOS_WIKIAVES)})"
            )
    no_system = _placeholders(p.system)
    esperado = {"vocabulario"} if p.vocabulario else set()
    if no_system != esperado:
        erros.append(f"system: placeholders {sorted(no_system)}, esperado {sorted(esperado)}")
    na_entrada = _placeholders(p.entrada)
    if na_entrada != set(p.campos):
        erros.append(f"entrada: placeholders {sorted(na_entrada)} diferentes de campos {p.campos}")
    return erros


def carregar_prompt(path: Path | str, vocabulario: Vocabulario, schemas: set[str]) -> Prompt:
    path = Path(path)
    try:
        dados = _ler_yaml(path)
    except VocabularioInvalido as e:
        raise PromptInvalido(path, e.erros) from e
    try:
        prompt = Prompt.model_validate(dados)
    except ValidationError as e:
        raise PromptInvalido(path, _erros_pydantic(e)) from e
    erros = _erros_de_conteudo(prompt, vocabulario, schemas)
    if prompt.id != path.stem:
        erros.append(f"id: {prompt.id!r} diferente do nome do arquivo ({path.stem!r})")
    if erros:
        raise PromptInvalido(path, erros)
    return prompt


def carregar_prompts(
    pasta: Path | str, vocabulario: Vocabulario, schemas: set[str]
) -> list[Prompt]:
    """Os três prompts do builder, na ordem b01, b02, b03."""
    pasta = Path(pasta)
    faltando = [i for i in PROMPTS_DO_BUILDER if not (pasta / f"{i}.yaml").exists()]
    if faltando:
        raise PromptInvalido(pasta, [f"arquivo {i}.yaml não encontrado" for i in faltando])
    return [carregar_prompt(pasta / f"{i}.yaml", vocabulario, schemas) for i in PROMPTS_DO_BUILDER]
