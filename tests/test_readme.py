"""O README confere com a CLI e com o settings (sem rede, sem banco).

O README é o manual de reprodução do piloto (Marco 7). Estes testes falham quando
um comando, uma opção, uma fonte ou uma variável de ambiente citada nele deixa de
existir, ou quando um comando novo da CLI não aparece nele.
"""

import re
import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

from avesrag_builder.cli import Fonte, app
from avesrag_builder.core.settings import Settings

README = Path(__file__).resolve().parents[1] / "README.md"
TEXTO = README.read_text(encoding="utf-8")
PREFIXO = "poetry run avesrag-builder"

# Variáveis do README que não são do settings: lidas pelo docker-compose.
SO_DO_COMPOSE = {"MONGODB_PORT"}

runner = CliRunner()


def _blocos_bash(texto: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", texto, flags=re.S)


def _comandos(texto: str) -> list[list[str]]:
    """Argumentos de cada `poetry run avesrag-builder ...` dos blocos bash, sem comentários."""
    comandos = []
    for bloco in _blocos_bash(texto):
        for linha in bloco.splitlines():
            linha = linha.split("#", 1)[0].strip()
            if linha.startswith(PREFIXO):
                comandos.append(shlex.split(linha.removeprefix(PREFIXO)))
    return comandos


COMANDOS = _comandos(TEXTO)


def _id(args: list[str]) -> str:
    return " ".join(args) or "(vazio)"


def test_o_readme_tem_a_sequencia_do_piloto():
    assert len(COMANDOS) >= 15
    for esperado in (["resolve"], ["extract", "--piloto"], ["index", "--fumaca"]):
        assert esperado in COMANDOS, f"falta `avesrag-builder {_id(esperado)}` no README"


@pytest.mark.parametrize("args", COMANDOS, ids=[_id(c) for c in COMANDOS])
def test_comando_e_opcoes_existem(args):
    assert args, "linha do README sem comando"
    resultado = runner.invoke(app, [*args, "--help"])
    assert resultado.exit_code == 0, (
        f"`avesrag-builder {_id(args)}` não existe:\n{resultado.output}"
    )
    for token in args:
        if token.startswith("--"):
            assert token in resultado.output, f"opção {token} não existe em `{args[0]}`"


@pytest.mark.parametrize("args", [c for c in COMANDOS if c[0] == "ingest"], ids=lambda c: _id(c))
def test_fonte_do_ingest_existe(args):
    fontes = {f.value for f in Fonte}
    posicionais = [t for t in args[1:] if not t.startswith("--")]
    assert posicionais, "ingest sem fonte no README"
    assert posicionais[0] in fontes, f"fonte {posicionais[0]!r} não existe: {sorted(fontes)}"


def test_toda_fonte_tem_ingest_no_readme():
    no_readme = {c[1] for c in COMANDOS if c[0] == "ingest" and len(c) > 1}
    assert {f.value for f in Fonte} <= no_readme


def test_todo_comando_da_cli_aparece_no_readme():
    da_cli = {c.name or c.callback.__name__ for c in app.registered_commands}
    citados = {c[0] for c in COMANDOS} | set(re.findall(r"\| `(\w+)[ `]", TEXTO))
    assert da_cli <= citados, f"faltam no README: {sorted(da_cli - citados)}"


def _variaveis_do_readme(texto: str) -> set[str]:
    secao = texto.split("### Variáveis de ambiente", 1)[1].split("\n### ", 1)[0]
    return set(re.findall(r"`([A-Z][A-Z0-9_]+)`", secao))


def test_variaveis_do_readme_existem_no_settings():
    citadas = _variaveis_do_readme(TEXTO) - SO_DO_COMPOSE - {"AVESRAG_LOG_FILE"}
    assert citadas, "seção de variáveis vazia"
    faltam = citadas - set(Settings.model_fields)
    assert not faltam, f"o README cita variáveis que o settings não tem: {sorted(faltam)}"


def test_variaveis_do_settings_estao_no_readme():
    # Caminhos de arquivos de data/raw/ e de config/ não são para quem reproduz o piloto.
    internas = {f for f in Settings.model_fields if f.endswith(("_XLSX", "_CSV", "_DIR"))}
    faltam = set(Settings.model_fields) - internas - _variaveis_do_readme(TEXTO)
    assert not faltam, f"variáveis do settings sem linha no README: {sorted(faltam)}"


def test_arquivos_de_config_citados_existem():
    raiz = README.parent
    for caminho in sorted(set(re.findall(r"`(config/[\w/.-]+\.ya?ml)`", TEXTO))):
        assert (raiz / caminho).is_file(), f"{caminho} citado no README não existe"
