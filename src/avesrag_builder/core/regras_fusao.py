"""Leitura e validação de `config/regras_fusao.yaml`.

Os cortes de tamanho e os critérios de `apta` ficam fora do `vocabulario.yaml`
porque são só do builder: o vocabulário também vai para o chat. O arquivo se
valida contra o vocabulário ao carregar, no padrão de `core/vocabulario.py`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import (
    Vocabulario,
    VocabularioInvalido,
    _erros_pydantic,
    _ler_yaml,
    vocabulario_padrao,
)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cortes(_Base):
    cortes: list[float] = Field(min_length=1)
    tolerancia: float = Field(ge=0, lt=0.5)


class Tamanho(_Base):
    faixas: list[str] = Field(min_length=2)
    comprimento_cm: Cortes
    massa_g: Cortes


class LimitesComprimento(_Base):
    min: float = Field(gt=0)
    max: float = Field(gt=0)
    arredondamento: float = Field(gt=0)


class Apta(_Base):
    minimos: dict[str, int] = Field(min_length=1)
    textos_b03: list[str] = Field(default_factory=list)


class RegrasFusaoArquivo(_Base):
    versao: str
    tamanho: Tamanho
    comprimento_cm: LimitesComprimento
    apta: Apta


TEXTOS_B03 = ("aparencia", "comportamento_ambiente", "voz_habitos")


class RegrasFusao:
    """Regras numéricas da fusão e da validação, conferidas contra o vocabulário."""

    def __init__(
        self,
        arquivo: RegrasFusaoArquivo,
        vocabulario: Vocabulario,
        origem: Path | str = "<memória>",
    ):
        self.arquivo = arquivo
        self.origem = str(origem)
        self.versao = arquivo.versao
        erros: list[str] = []

        tam = arquivo.tamanho
        for faixa in tam.faixas:
            if not vocabulario.contem("tamanho", faixa):
                erros.append(f"tamanho.faixas: {faixa!r} não é valor de tamanho")
        for nome in ("comprimento_cm", "massa_g"):
            cortes = getattr(tam, nome).cortes
            if len(cortes) != len(tam.faixas) - 1:
                erros.append(
                    f"tamanho.{nome}.cortes: {len(tam.faixas)} faixas pedem "
                    f"{len(tam.faixas) - 1} cortes"
                )
            if any(b <= a for a, b in zip(cortes, cortes[1:], strict=False)) or cortes[0] <= 0:
                erros.append(f"tamanho.{nome}.cortes: use valores positivos e crescentes")

        lim = arquivo.comprimento_cm
        if lim.min >= lim.max:
            erros.append("comprimento_cm: min deve ser menor que max")

        atributos = set(vocabulario.atributos)
        for atributo, n in arquivo.apta.minimos.items():
            if atributo not in atributos:
                erros.append(f"apta.minimos.{atributo}: não é atributo do vocabulário")
            if n < 1:
                erros.append(f"apta.minimos.{atributo}: use 1 ou mais")
        for texto in arquivo.apta.textos_b03:
            if texto not in TEXTOS_B03:
                erros.append(f"apta.textos_b03: {texto!r} não é texto do b03 {list(TEXTOS_B03)}")

        if erros:
            raise VocabularioInvalido(self.origem, erros)

    # -- tamanho --------------------------------------------------------------

    def _faixas(self, valor: float, cortes: Cortes) -> list[str]:
        """Faixa do valor e, a menos da tolerância de um corte, a faixa vizinha."""
        faixas = self.arquivo.tamanho.faixas
        indice = sum(1 for c in cortes.cortes if valor >= c)
        escolhidas = {indice}
        for i, corte in enumerate(cortes.cortes):
            if abs(valor - corte) <= cortes.tolerancia * corte:
                escolhidas |= {i, i + 1}
        return [faixas[i] for i in sorted(escolhidas)]

    def tamanho_por_comprimento(self, comprimento_cm: float) -> list[str]:
        return self._faixas(comprimento_cm, self.arquivo.tamanho.comprimento_cm)

    def tamanho_por_massa(self, massa_g: float) -> list[str]:
        return self._faixas(massa_g, self.arquivo.tamanho.massa_g)

    # -- comprimento ----------------------------------------------------------

    def arredondar_comprimento(self, valor: float) -> float:
        passo = self.arquivo.comprimento_cm.arredondamento
        return round(round(valor / passo) * passo, 2)

    def comprimento_valido(self, valor: float) -> bool:
        lim = self.arquivo.comprimento_cm
        return lim.min <= valor <= lim.max

    # -- apta -----------------------------------------------------------------

    @property
    def minimos(self) -> dict[str, int]:
        return dict(self.arquivo.apta.minimos)

    @property
    def textos_b03(self) -> list[str]:
        return list(self.arquivo.apta.textos_b03)


def carregar_regras_fusao(path: Path | str, vocabulario: Vocabulario) -> RegrasFusao:
    path = Path(path)
    data = _ler_yaml(path)
    try:
        arquivo = RegrasFusaoArquivo.model_validate(data)
    except ValidationError as e:
        raise VocabularioInvalido(path, _erros_pydantic(e)) from e
    return RegrasFusao(arquivo, vocabulario, origem=path)


@lru_cache
def regras_fusao_padrao() -> RegrasFusao:
    return carregar_regras_fusao(
        get_settings().CONFIG_DIR / "regras_fusao.yaml", vocabulario_padrao()
    )
