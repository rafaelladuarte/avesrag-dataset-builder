"""Leitura e validação de `config/regras_midia.yaml`.

Regras da foto de cada espécie (`midia.foto`): a ordem das fontes, as licenças
aceitas e como reconhecer, no Commons, uma imagem que não é foto ou um autor sem
nome. O arquivo se valida ao carregar, no padrão de `core/regras_fusao.py`.
"""

from __future__ import annotations

import re
import string
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from avesrag_builder.core.models import FonteFoto
from avesrag_builder.core.settings import get_settings
from avesrag_builder.core.vocabulario import VocabularioInvalido, _erros_pydantic, _ler_yaml

# Métodos de escolha que cada fonte sabe fazer (plano_fotos.md §4).
METODOS: dict[str, set[str]] = {"inaturalist": {"brasil", "mundo"}, "commons": {"p18"}}
CAMPOS_CREDITO = {"autor", "licenca", "fonte"}
# Licenças recusadas pela decisão 2: NC, ND e GFDL (no nome ou em um apelido).
_RECUSADA = re.compile(r"(^|[\s-])(nc|nd)([\s-]|$)|gfdl", re.IGNORECASE)
# Sufixo de jurisdição de uma licença portada: "CC BY-SA 2.5 ar".
_PORTADA = re.compile(r"^(.*\d\.\d)\s+[a-z]{2,3}$")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemOrdem(_Base):
    fonte: FonteFoto
    metodo: str


class Licenca(_Base):
    nome: str = Field(min_length=1)
    url: str
    inaturalist: list[str] = Field(default_factory=list)
    commons: list[str] = Field(default_factory=list)


class NaoFoto(_Base):
    categorias: list[str] = Field(default_factory=list)
    artistas: list[str] = Field(default_factory=list)


class RegrasCommons(_Base):
    aceitar_portadas: bool = False
    nao_foto: NaoFoto = Field(default_factory=NaoFoto)
    autor_invalido: list[str] = Field(default_factory=list)


class RegrasMidiaArquivo(_Base):
    versao: str
    ordem: list[ItemOrdem] = Field(min_length=1)
    nomes_exibicao: dict[FonteFoto, str]
    credito: str
    licencas: list[Licenca] = Field(min_length=1)
    commons: RegrasCommons = Field(default_factory=RegrasCommons)


def _normalizar(texto: str) -> str:
    return " ".join(texto.split()).casefold()


def _compilar(padroes: list[str], caminho: str, erros: list[str]) -> list[re.Pattern[str]]:
    compiladas = []
    for i, padrao in enumerate(padroes):
        try:
            compiladas.append(re.compile(padrao, re.IGNORECASE))
        except re.error as e:
            erros.append(f"{caminho}[{i}]: expressão inválida {padrao!r} ({e})")
    return compiladas


class RegrasMidia:
    """Regras da foto, conferidas ao carregar."""

    def __init__(self, arquivo: RegrasMidiaArquivo, origem: Path | str = "<memória>"):
        self.arquivo = arquivo
        self.origem = str(origem)
        self.versao = arquivo.versao
        erros: list[str] = []

        vistos: set[tuple[str, str]] = set()
        for i, item in enumerate(arquivo.ordem):
            if item.metodo not in METODOS[item.fonte]:
                erros.append(
                    f"ordem[{i}]: {item.fonte} não tem o método {item.metodo!r} "
                    f"(use {sorted(METODOS[item.fonte])})"
                )
            if (item.fonte, item.metodo) in vistos:
                erros.append(f"ordem[{i}]: {item.fonte}/{item.metodo} repetido")
            vistos.add((item.fonte, item.metodo))

        for fonte in {item.fonte for item in arquivo.ordem}:
            if not (arquivo.nomes_exibicao.get(fonte) or "").strip():
                erros.append(f"nomes_exibicao: falta o nome de {fonte}")

        try:
            campos = {c for _, c, _, _ in string.Formatter().parse(arquivo.credito) if c}
        except ValueError as e:
            campos = set()
            erros.append(f"credito: modelo inválido ({e})")
        for falta in sorted({"autor", "licenca"} - campos):
            erros.append(f"credito: o modelo precisa citar {{{falta}}}")
        for sobra in sorted(campos - CAMPOS_CREDITO):
            erros.append(f"credito: {{{sobra}}} não existe (use {sorted(CAMPOS_CREDITO)})")

        self._por_inat: dict[str, Licenca] = {}
        self._por_commons: dict[str, Licenca] = {}
        nomes: set[str] = set()
        for i, lic in enumerate(arquivo.licencas):
            caminho = f"licencas[{i}] ({lic.nome})"
            if lic.nome in nomes:
                erros.append(f"{caminho}: nome repetido")
            nomes.add(lic.nome)
            if not lic.url.startswith("https://"):
                erros.append(f"{caminho}: a URL deve começar com https://")
            for termo in [lic.nome, *lic.inaturalist, *lic.commons]:
                if _RECUSADA.search(termo):
                    erros.append(f"{caminho}: {termo!r} é NC, ND ou GFDL, recusada pelo plano")
            for fonte, apelidos, indice in (
                ("inaturalist", lic.inaturalist, self._por_inat),
                ("commons", lic.commons, self._por_commons),
            ):
                for apelido in apelidos:
                    chave = _normalizar(apelido)
                    if chave in indice and indice[chave] is not lic:
                        erros.append(
                            f"{caminho}: {fonte} {apelido!r} já é de {indice[chave].nome!r}"
                        )
                    indice[chave] = lic

        c = arquivo.commons
        self._categorias = _compilar(c.nao_foto.categorias, "commons.nao_foto.categorias", erros)
        self._artistas = _compilar(c.nao_foto.artistas, "commons.nao_foto.artistas", erros)
        self._autor_invalido = _compilar(c.autor_invalido, "commons.autor_invalido", erros)

        if erros:
            raise VocabularioInvalido(self.origem, erros)

    # -- ordem e crédito --------------------------------------------------------

    @property
    def ordem(self) -> list[tuple[str, str]]:
        return [(item.fonte, item.metodo) for item in self.arquivo.ordem]

    def nome_exibicao(self, fonte: str) -> str:
        return self.arquivo.nomes_exibicao[fonte]

    def credito(self, autor: str, licenca: str, fonte: str) -> str:
        return self.arquivo.credito.format(
            autor=autor.strip(), licenca=licenca, fonte=self.nome_exibicao(fonte)
        )

    # -- licenças ---------------------------------------------------------------

    def licenca_inaturalist(self, codigo: str | None) -> Licenca | None:
        """`license_code` da API do iNaturalist -> licença aceita, ou None."""
        return self._por_inat.get(_normalizar(codigo)) if codigo else None

    def licenca_commons(self, nome: str | None) -> Licenca | None:
        """`LicenseShortName` do Commons -> licença aceita, ou None."""
        if not nome:
            return None
        chave = _normalizar(nome)
        if chave in self._por_commons:
            return self._por_commons[chave]
        portada = _PORTADA.match(chave)
        if self.arquivo.commons.aceitar_portadas and portada:
            return self._por_commons.get(portada.group(1))
        return None

    # -- Commons: foto e autor --------------------------------------------------

    def nao_e_foto_commons(self, categorias: Iterable[str], artista: str | None) -> bool:
        """True se a imagem do Commons é ilustração, exemplar de museu etc."""
        if any(p.search(cat) for cat in categorias for p in self._categorias):
            return True
        return bool(artista) and any(p.search(artista) for p in self._artistas)

    def autor_valido(self, autor: str | None) -> bool:
        return bool(autor and autor.strip()) and not any(
            p.search(autor) for p in self._autor_invalido
        )


def carregar_regras_midia(path: Path | str) -> RegrasMidia:
    path = Path(path)
    data = _ler_yaml(path)
    try:
        arquivo = RegrasMidiaArquivo.model_validate(data)
    except ValidationError as e:
        raise VocabularioInvalido(path, _erros_pydantic(e)) from e
    return RegrasMidia(arquivo, origem=path)


@lru_cache
def regras_midia_padrao() -> RegrasMidia:
    return carregar_regras_midia(get_settings().CONFIG_DIR / "regras_midia.yaml")
