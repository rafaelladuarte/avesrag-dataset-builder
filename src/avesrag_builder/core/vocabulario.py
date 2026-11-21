"""Leitura e validação de `config/vocabulario.yaml` e `config/regras_bico.yaml`.

Os dois arquivos se validam ao carregar: um erro de digitação no YAML falha
aqui, com o caminho do problema, e não vira um valor fora do vocabulário na
base. `vocabulario_padrao()` e `regras_bico_padrao()` carregam os arquivos de
`config/` uma vez por processo.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.texto import normalizar_termo

VALOR_RE = re.compile(r"^([a-z][a-z0-9_]*|[A-Z]{2})$")

ATRIBUTO_CORES_POR_PARTE = "cores_por_parte"


class VocabularioInvalido(ValueError):
    """O arquivo de vocabulário ou de regras não passou na validação."""

    def __init__(self, arquivo: Path | str, erros: list[str]):
        self.arquivo = str(arquivo)
        self.erros = erros
        lista = "\n".join(f"  - {e}" for e in erros)
        super().__init__(f"{self.arquivo}: {len(erros)} erro(s)\n{lista}")


# ---------------------------------------------------------------------------
# YAML sem chaves duplicadas
# ---------------------------------------------------------------------------


class _LoaderSemDuplicadas(yaml.SafeLoader):
    pass


def _mapping_sem_duplicadas(loader: yaml.SafeLoader, node: yaml.MappingNode, deep=False):
    chaves = set()
    for chave_node, _ in node.value:
        chave = loader.construct_object(chave_node, deep=deep)
        if chave in chaves:
            raise yaml.constructor.ConstructorError(
                None, None, f"chave duplicada: {chave!r}", chave_node.start_mark
            )
        chaves.add(chave)
    return loader.construct_mapping(node, deep=deep)


_LoaderSemDuplicadas.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping_sem_duplicadas
)


def _ler_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.load(f, Loader=_LoaderSemDuplicadas)
    except yaml.YAMLError as e:
        raise VocabularioInvalido(path, [f"YAML inválido: {e}"]) from e
    if not isinstance(data, dict):
        raise VocabularioInvalido(path, ["o arquivo deve ser um mapeamento YAML"])
    return data


def _erros_pydantic(e: ValidationError) -> list[str]:
    return [".".join(str(p) for p in err["loc"]) + f": {err['msg']}" for err in e.errors()]


# ---------------------------------------------------------------------------
# Schema dos arquivos
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValorVocab(_Base):
    descricao: str = Field(min_length=1)
    sinonimos: list[str] = Field(default_factory=list)
    grupo: str | None = None


class AtributoVocab(_Base):
    descricao: str = Field(min_length=1)
    multiplo: bool = True
    grupos: list[str] | None = None
    valores: dict[str, ValorVocab] = Field(min_length=1)


class CoresPorParte(_Base):
    descricao: str = Field(min_length=1)
    cor: str
    partes: dict[str, ValorVocab] = Field(min_length=1)


class Mapeamento(_Base):
    origem: str = Field(min_length=1)
    destino: str
    valores: dict[str, list[str] | None]


class VocabularioArquivo(_Base):
    versao: str
    atributos: dict[str, AtributoVocab] = Field(min_length=1)
    cores_por_parte: CoresPorParte
    mapeamentos: dict[str, Mapeamento] = Field(default_factory=dict)


class PerfilBico(_Base):
    comprimento: list[str] = Field(min_length=1)
    espessura: list[str] = Field(min_length=1)
    curvatura: list[str] = Field(min_length=1)
    extra: list[str] = Field(default_factory=list)
    exemplo: str | None = None


class MapeamentoDieta(_Base):
    origem: str = Field(min_length=1)
    valores: dict[str, str | None]


class RegrasBicoArquivo(_Base):
    versao: str
    por_familia: dict[str, str]
    por_dieta: dict[str, MapeamentoDieta]
    dimensoes: dict[str, list[str]]
    perfil_visual: dict[str, PerfilBico]


# ---------------------------------------------------------------------------
# Vocabulário
# ---------------------------------------------------------------------------


def _indice_de_termos(
    nome: str, valores: dict[str, ValorVocab], erros: list[str]
) -> dict[str, str]:
    """termo normalizado -> valor; registra colisões entre valores diferentes."""
    indice: dict[str, str] = {}
    for valor, info in valores.items():
        for termo in [valor, *info.sinonimos]:
            chave = normalizar_termo(termo)
            if not chave:
                erros.append(f"{nome}.{valor}: sinônimo vazio")
                continue
            anterior = indice.get(chave)
            if anterior is not None and anterior != valor:
                erros.append(f"{nome}: o termo {termo!r} aponta para {anterior!r} e para {valor!r}")
            indice.setdefault(chave, valor)
    return indice


class Vocabulario:
    """Vocabulário carregado e validado."""

    def __init__(self, arquivo: VocabularioArquivo, origem: Path | str = "<memória>"):
        self.arquivo = arquivo
        self.origem = str(origem)
        self.versao = arquivo.versao
        erros: list[str] = []
        self._indices: dict[str, dict[str, str]] = {}

        for nome, atributo in arquivo.atributos.items():
            if nome == ATRIBUTO_CORES_POR_PARTE:
                erros.append(f"atributos.{nome}: declare em `cores_por_parte`, fora de `atributos`")
            for valor, info in atributo.valores.items():
                if not VALOR_RE.match(valor):
                    erros.append(f"atributos.{nome}.{valor}: use snake_case ASCII")
                if atributo.grupos is None and info.grupo is not None:
                    erros.append(f"atributos.{nome}.{valor}: `grupo` sem `grupos` no atributo")
                if atributo.grupos is not None and info.grupo not in atributo.grupos:
                    erros.append(
                        f"atributos.{nome}.{valor}: grupo {info.grupo!r} não está em {atributo.grupos}"
                    )
            self._indices[nome] = _indice_de_termos(f"atributos.{nome}", atributo.valores, erros)

        cpp = arquivo.cores_por_parte
        for parte in cpp.partes:
            if not VALOR_RE.match(parte):
                erros.append(f"cores_por_parte.partes.{parte}: use snake_case ASCII")
        self._indice_partes = _indice_de_termos("cores_por_parte.partes", cpp.partes, erros)
        if cpp.cor not in arquivo.atributos:
            erros.append(f"cores_por_parte.cor: atributo {cpp.cor!r} não existe")

        for origem_map, mapa in arquivo.mapeamentos.items():
            destino = arquivo.atributos.get(mapa.destino)
            if destino is None:
                erros.append(
                    f"mapeamentos.{origem_map}.destino: atributo {mapa.destino!r} não existe"
                )
                continue
            for valor_fonte, alvos in mapa.valores.items():
                if alvos is None:
                    continue
                if not alvos:
                    erros.append(
                        f"mapeamentos.{origem_map}.{valor_fonte}: lista vazia (use null para 'sem correspondência')"
                    )
                for alvo in alvos:
                    if alvo not in destino.valores:
                        erros.append(
                            f"mapeamentos.{origem_map}.{valor_fonte}: {alvo!r} não é valor de {mapa.destino}"
                        )

        if erros:
            raise VocabularioInvalido(self.origem, erros)

    # -- consulta -------------------------------------------------------------

    @property
    def atributos(self) -> list[str]:
        return list(self.arquivo.atributos)

    def _atributo(self, atributo: str) -> AtributoVocab:
        try:
            return self.arquivo.atributos[atributo]
        except KeyError:
            raise KeyError(f"atributo desconhecido: {atributo!r}") from None

    def valores(self, atributo: str) -> list[str]:
        return list(self._atributo(atributo).valores)

    def multiplo(self, atributo: str) -> bool:
        return self._atributo(atributo).multiplo

    def partes(self) -> list[str]:
        return list(self.arquivo.cores_por_parte.partes)

    def contem(self, atributo: str, valor: str) -> bool:
        return valor in self._atributo(atributo).valores

    @staticmethod
    def _buscar(indice: dict[str, str], termo: str) -> str | None:
        chave = normalizar_termo(termo)
        # Plural simples: "pretas" -> "preta", "olivaceas" -> "olivacea".
        singular = " ".join(p[:-1] if len(p) > 3 and p.endswith("s") else p for p in chave.split())
        for candidata in dict.fromkeys([chave, singular]):
            if candidata in indice:
                return indice[candidata]
        # Termo composto: "cinza escuro" -> "cinza", "marrom avermelhado" -> "marrom".
        for candidata in dict.fromkeys([chave, singular]):
            palavras = candidata.split(" ")
            for fim in range(len(palavras) - 1, 0, -1):
                prefixo = " ".join(palavras[:fim])
                if prefixo in indice:
                    return indice[prefixo]
        return None

    def normalizar(self, atributo: str, termo: str) -> str | None:
        """Valor do vocabulário para um termo livre, ou None se não reconhecido."""
        self._atributo(atributo)
        return self._buscar(self._indices[atributo], termo)

    def normalizar_parte(self, termo: str) -> str | None:
        return self._buscar(self._indice_partes, termo)

    def mapear(self, origem: str, valor_fonte: str) -> list[str] | None:
        """Valores do vocabulário para uma categoria da fonte (None = sem correspondência)."""
        try:
            mapa = self.arquivo.mapeamentos[origem]
        except KeyError:
            raise KeyError(f"mapeamento desconhecido: {origem!r}") from None
        alvos = mapa.valores.get(valor_fonte)
        return list(alvos) if alvos else None

    def para_prompt(self, atributos: list[str]) -> str:
        """Bloco "Valores permitidos" para injetar nos prompts (Marco 4)."""
        linhas = []
        for nome in atributos:
            if nome == ATRIBUTO_CORES_POR_PARTE:
                cpp = self.arquivo.cores_por_parte
                linhas.append(
                    f"- {nome}: parte ∈ {', '.join(cpp.partes)}; cor ∈ valores de {cpp.cor}"
                )
                continue
            attr = self._atributo(nome)
            valores = "; ".join(f"{v} ({info.descricao})" for v, info in attr.valores.items())
            qtd = "um ou mais" if attr.multiplo else "um"
            linhas.append(f"- {nome} ({qtd}): {valores}")
        return "\n".join(linhas)


def carregar_vocabulario(path: Path | str) -> Vocabulario:
    path = Path(path)
    data = _ler_yaml(path)
    try:
        arquivo = VocabularioArquivo.model_validate(data)
    except ValidationError as e:
        raise VocabularioInvalido(path, _erros_pydantic(e)) from e
    return Vocabulario(arquivo, origem=path)


@lru_cache
def vocabulario_padrao() -> Vocabulario:
    return carregar_vocabulario(get_settings().CONFIG_DIR / "vocabulario.yaml")


# ---------------------------------------------------------------------------
# Regras de bico
# ---------------------------------------------------------------------------


class RegrasBico:
    """Regras de `bico_tipo` carregadas e validadas contra o vocabulário."""

    def __init__(
        self, arquivo: RegrasBicoArquivo, vocabulario: Vocabulario, origem: Path | str = "<memória>"
    ):
        self.arquivo = arquivo
        self.origem = str(origem)
        self.versao = arquivo.versao
        erros: list[str] = []

        if "bico_tipo" not in vocabulario.atributos:
            raise VocabularioInvalido(self.origem, ["o vocabulário não tem o atributo bico_tipo"])
        tipos = set(vocabulario.valores("bico_tipo"))

        for familia, tipo in arquivo.por_familia.items():
            if tipo not in tipos:
                erros.append(f"por_familia.{familia}: {tipo!r} não é valor de bico_tipo")

        for origem_map, mapa in arquivo.por_dieta.items():
            for valor_fonte, tipo in mapa.valores.items():
                if tipo is not None and tipo not in tipos:
                    erros.append(
                        f"por_dieta.{origem_map}.{valor_fonte}: {tipo!r} não é valor de bico_tipo"
                    )

        dimensoes_esperadas = {"comprimento", "espessura", "curvatura", "extra"}
        if set(arquivo.dimensoes) != dimensoes_esperadas:
            erros.append(f"dimensoes: esperado exatamente {sorted(dimensoes_esperadas)}")

        for tipo in sorted(tipos - set(arquivo.perfil_visual)):
            erros.append(f"perfil_visual: falta o perfil de {tipo!r}")
        for tipo, perfil in arquivo.perfil_visual.items():
            if tipo not in tipos:
                erros.append(f"perfil_visual.{tipo}: não é valor de bico_tipo")
            for dimensao in dimensoes_esperadas:
                aceitos = arquivo.dimensoes.get(dimensao, [])
                for valor in getattr(perfil, dimensao):
                    if valor not in aceitos:
                        erros.append(
                            f"perfil_visual.{tipo}.{dimensao}: {valor!r} não está em dimensoes.{dimensao}"
                        )

        if erros:
            raise VocabularioInvalido(self.origem, erros)

    def tipo_por_familia(self, familia: str) -> str | None:
        return self.arquivo.por_familia.get(familia)

    def tipo_por_dieta(self, origem: str, valor_fonte: str) -> str | None:
        try:
            mapa = self.arquivo.por_dieta[origem]
        except KeyError:
            raise KeyError(f"mapeamento de dieta desconhecido: {origem!r}") from None
        return mapa.valores.get(valor_fonte)

    def perfil(self, tipo: str) -> PerfilBico:
        return self.arquivo.perfil_visual[tipo]


def carregar_regras_bico(path: Path | str, vocabulario: Vocabulario) -> RegrasBico:
    path = Path(path)
    data = _ler_yaml(path)
    try:
        arquivo = RegrasBicoArquivo.model_validate(data)
    except ValidationError as e:
        raise VocabularioInvalido(path, _erros_pydantic(e)) from e
    return RegrasBico(arquivo, vocabulario, origem=path)


@lru_cache
def regras_bico_padrao() -> RegrasBico:
    return carregar_regras_bico(
        get_settings().CONFIG_DIR / "regras_bico.yaml", vocabulario_padrao()
    )
