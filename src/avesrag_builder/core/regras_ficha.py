"""Leitura e validação de `config/regras_ficha.yaml`.

Traduz a dieta das fontes (AVONET e BIRDBASE) para o texto da ficha. O arquivo se
valida ao carregar, no padrão dos outros `config/regras_*.yaml`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import VocabularioInvalido, _erros_pydantic, _ler_yaml

FONTES_DIETA = ("avonet", "birdbase")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TabelasDieta(_Base):
    avonet: dict[str, str | None]
    birdbase: dict[str, str | None]


class RegrasFichaArquivo(_Base):
    versao: str
    ordem_dieta: list[str] = Field(min_length=1)
    dieta: TabelasDieta


class RegrasFicha:
    def __init__(self, arquivo: RegrasFichaArquivo, origem: Path | str = "<memória>"):
        erros = []
        for fonte in arquivo.ordem_dieta:
            if fonte not in FONTES_DIETA:
                erros.append(f"ordem_dieta: {fonte!r} não existe (use {list(FONTES_DIETA)})")
        if len(set(arquivo.ordem_dieta)) != len(arquivo.ordem_dieta):
            erros.append("ordem_dieta: fonte repetida")
        for fonte in FONTES_DIETA:
            for categoria, texto in getattr(arquivo.dieta, fonte).items():
                if texto is not None and not texto.strip():
                    erros.append(f"dieta.{fonte}.{categoria}: texto vazio (use null)")
        if erros:
            raise VocabularioInvalido(origem, erros)
        self.arquivo = arquivo
        self.versao = arquivo.versao
        self.origem = str(origem)

    def dieta(self, avonet: str | None, birdbase: str | None) -> tuple[str, str] | None:
        """(texto, fonte) da primeira fonte da ordem cuja categoria tem texto."""
        categorias = {"avonet": avonet, "birdbase": birdbase}
        for fonte in self.arquivo.ordem_dieta:
            categoria = (categorias[fonte] or "").strip()
            texto = getattr(self.arquivo.dieta, fonte).get(categoria) if categoria else None
            if texto:
                return texto, fonte
        return None


def carregar_regras_ficha(path: Path) -> RegrasFicha:
    bruto = _ler_yaml(path)
    try:
        return RegrasFicha(RegrasFichaArquivo.model_validate(bruto), path)
    except ValidationError as e:
        raise VocabularioInvalido(path, _erros_pydantic(e)) from e


@lru_cache
def regras_ficha_padrao() -> RegrasFicha:
    return carregar_regras_ficha(get_settings().CONFIG_DIR / "regras_ficha.yaml")
