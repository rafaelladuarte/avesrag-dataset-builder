"""Testes para avesrag_builder.core.settings."""

import pytest

from avesrag_builder.core.settings import (
    ROOT_DIR,
    MissingSettingError,
    Settings,
    get_settings,
)

VARIAVEIS = [
    "OPENAI_API_KEY",
    "EBIRD_API_KEY",
    "MONGODB_URI",
    "MONGODB_DATABASE",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "PILOTO_MUNICIPIO_IBGE",
    "WIKIAVES_MAX_ESPECIES",
]


@pytest.fixture
def ambiente_vazio(monkeypatch):
    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)


def test_carrega_sem_variaveis(ambiente_vazio):
    s = Settings(_env_file=None)
    assert s.OPENAI_API_KEY is None
    assert s.EBIRD_API_KEY is None


def test_padroes_da_especificacao(ambiente_vazio):
    s = Settings(_env_file=None)
    assert s.MONGODB_URI == "mongodb://localhost:27017/?directConnection=true"
    assert s.MONGODB_DATABASE == "avesrag"
    assert s.LLM_PROVIDER == "openai"
    assert s.LLM_MODEL == "gpt-6-luna"
    assert s.EMBEDDING_MODEL == "text-embedding-3-large"
    assert s.PILOTO_MUNICIPIO_IBGE == "3170206"


def test_le_do_ambiente(ambiente_vazio, monkeypatch):
    monkeypatch.setenv("MONGODB_DATABASE", "teste")
    monkeypatch.setenv("EBIRD_API_KEY", "abc")
    s = Settings(_env_file=None)
    assert s.MONGODB_DATABASE == "teste"
    assert s.EBIRD_API_KEY.get_secret_value() == "abc"


def test_chave_nao_aparece_no_repr(ambiente_vazio, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-segredo")
    assert "sk-segredo" not in repr(Settings(_env_file=None))


def test_require_lista_as_ausentes(ambiente_vazio):
    s = Settings(_env_file=None)
    with pytest.raises(MissingSettingError, match="OPENAI_API_KEY, EBIRD_API_KEY"):
        s.require("OPENAI_API_KEY", "EBIRD_API_KEY")


def test_require_aceita_preenchidas(ambiente_vazio, monkeypatch):
    monkeypatch.setenv("EBIRD_API_KEY", "abc")
    Settings(_env_file=None).require("EBIRD_API_KEY", "MONGODB_URI")


def test_get_settings_usa_cache():
    assert get_settings() is get_settings()


def test_caminhos_das_planilhas_existem(ambiente_vazio):
    s = Settings(_env_file=None)
    for caminho in (s.AVONET_XLSX, s.BIRDBASE_XLSX, s.CBRO_XLSX, s.IBGE_XLSX, s.WIKIAVES_CSV):
        assert caminho.is_file(), caminho
    assert s.CONFIG_DIR == ROOT_DIR / "config"
