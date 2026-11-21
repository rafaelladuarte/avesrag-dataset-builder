"""Testes para o CLI avesrag-builder."""

import pytest
from typer.testing import CliRunner

from avesrag_builder import __version__
from avesrag_builder.cli import app

COMANDOS = ["ingest", "resolve", "extract", "fuse", "validate", "docs", "index", "run"]
FONTES = ["wikiaves", "avonet", "birdbase", "cbro", "ebird", "ibge"]

runner = CliRunner()


@pytest.fixture(autouse=True)
def sem_env(monkeypatch):
    for nome in ("OPENAI_API_KEY", "EBIRD_API_KEY", "MONGODB_URI"):
        monkeypatch.delenv(nome, raising=False)


def test_help_lista_os_comandos():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for comando in COMANDOS:
        assert f"  {comando} " in result.output


def test_sem_argumentos_mostra_ajuda():
    result = runner.invoke(app, [])
    assert "Usage:" in result.output


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


@pytest.mark.parametrize("comando", COMANDOS)
def test_help_de_cada_comando(comando):
    result = runner.invoke(app, [comando, "--help"])
    assert result.exit_code == 0


def test_ingest_lista_as_fontes():
    result = runner.invoke(app, ["ingest", "--help"])
    assert "|".join(FONTES) in result.output


def test_ingest_fonte_invalida():
    result = runner.invoke(app, ["ingest", "xpto"])
    assert result.exit_code == 2
    assert "xpto" in result.output


@pytest.mark.parametrize(
    "args, marco",
    [
        (["resolve"], "Marco 3"),
        (["extract", "--piloto"], "Marco 4"),
        (["fuse"], "Marco 5"),
        (["validate"], "Marco 5"),
        (["docs"], "Marco 6"),
        (["run", "--piloto"], "Marco 6"),
    ],
)
def test_comandos_ainda_nao_implementados(args, marco):
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert marco in result.output


def test_log_level_invalido():
    result = runner.invoke(app, ["--log-level", "barulhento", "resolve"])
    assert result.exit_code == 2
    assert "nível de log inválido" in result.output


def test_index_sem_verificar_ainda_nao_implementado():
    result = runner.invoke(app, ["index"])
    assert result.exit_code == 2
    assert "Marco 6" in result.output


def test_index_verificar_reporta_falha(monkeypatch):
    from avesrag_builder.db import busca, connection

    def falha(db):
        raise busca.BuscaIndisponivel("sem mongot")

    monkeypatch.setattr(busca, "verificar_busca", falha)
    monkeypatch.setattr(connection, "get_db", lambda: None)
    result = runner.invoke(app, ["index", "--verificar"])
    assert result.exit_code == 1
    assert "Falhou: sem mongot" in result.output


def test_index_verificar_ok(monkeypatch):
    from avesrag_builder.db import busca, connection

    monkeypatch.setattr(
        busca, "verificar_busca", lambda db: busca.ResultadoVerificacao("8.3.17", ["a"], ["c"])
    )
    monkeypatch.setattr(connection, "get_db", lambda: None)
    result = runner.invoke(app, ["index", "--verificar"])
    assert result.exit_code == 0
    assert "MongoDB 8.3.17 aceita" in result.output


def test_ingest_rejeita_opcao_que_nao_se_aplica():
    result = runner.invoke(app, ["ingest", "cbro", "--refazer"])
    assert result.exit_code == 2
    assert "--refazer não se aplica a cbro" in result.output
