"""Integração: ingest ebird com a API simulada (pytest -m integration)."""

import pytest
import requests

from avesrag_builder.core.settings import Settings
from avesrag_builder.ingest import ebird

pytestmark = pytest.mark.integration

TAXA = [
    {"speciesCode": "grekis", "sciName": "Pitangus sulphuratus", "category": "species"},
    {"speciesCode": "grerhe1", "sciName": "Rhea americana", "category": "species"},
]
REGIOES = {"MG": [{"code": "BR-MG-825", "name": "Uberlândia"}], "GO": []}


@pytest.fixture
def api_falsa(monkeypatch):
    chamadas = []

    def regioes(uf):
        chamadas.append(("regioes", uf))
        return REGIOES.get(uf, [])

    def especies(codigo):
        chamadas.append(("spplist", codigo))
        if codigo == "BR-MG-FALHA":
            raise requests.HTTPError("500")
        return ["grerhe1", "grekis"]

    monkeypatch.setattr(ebird, "baixar_taxonomia", lambda: TAXA)
    monkeypatch.setattr(ebird, "baixar_regioes", regioes)
    monkeypatch.setattr(ebird, "baixar_especies", especies)
    monkeypatch.setattr(
        ebird,
        "municipios_ibge",
        lambda s: [
            {"geocodigo": "3170206", "nome": "Uberlândia", "uf": "MG"},
            {"geocodigo": "5200050", "nome": "Abadia de Goiás", "uf": "GO"},
        ],
    )
    return chamadas


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None, EBIRD_API_KEY="x", PILOTO_MUNICIPIO_IBGE="3170206", REPORTS_DIR=tmp_path
    )


def test_piloto_grava_taxonomia_e_um_municipio(db_temporario, api_falsa, settings):
    taxonomia, municipios = ebird.ingerir(db_temporario, piloto=True, settings=settings)
    assert taxonomia.inseridos == 2
    assert municipios.inseridos == 1
    doc = db_temporario.raw_ebird.find_one({"_id": "municipio:3170206"})
    assert doc["dados"]["especies"] == ["grerhe1", "grekis"]
    assert ("regioes", "GO") not in api_falsa

    # Segunda execução: nada muda na fonte, nada é gravado
    taxonomia, municipios = ebird.ingerir(db_temporario, piloto=True, settings=settings)
    assert taxonomia.gravados == municipios.gravados == 0


def test_completo_grava_sem_match_e_relatorio(db_temporario, api_falsa, settings):
    ebird.ingerir(db_temporario, settings=settings)
    goias = db_temporario.raw_ebird.find_one({"_id": "municipio:5200050"})["dados"]
    assert goias["match_type"] == "sem_match"
    assert goias["especies"] is None
    relatorio = (settings.REPORTS_DIR / "ebird_municipios_sem_match.tsv").read_text()
    assert "5200050\tAbadia de Goiás\tGO" in relatorio


def test_completo_pula_ja_gravados_sem_refazer(db_temporario, api_falsa, settings):
    ebird.ingerir(db_temporario, settings=settings)
    api_falsa.clear()
    ebird.ingerir(db_temporario, settings=settings)
    assert not [c for c in api_falsa if c[0] == "spplist"]
    ebird.ingerir(db_temporario, refazer=True, settings=settings)
    assert ("spplist", "BR-MG-825") in api_falsa


def test_falha_na_api_nao_vira_lista_vazia(db_temporario, api_falsa, settings, monkeypatch):
    REGIOES_FALHA = {"MG": [{"code": "BR-MG-FALHA", "name": "Uberlândia"}]}
    monkeypatch.setattr(ebird, "baixar_regioes", lambda uf: REGIOES_FALHA.get(uf, []))
    _, municipios = ebird.ingerir(db_temporario, piloto=True, settings=settings)
    assert municipios.erros and "BR-MG-FALHA" in municipios.erros[0]
    assert db_temporario.raw_ebird.find_one({"_id": "municipio:3170206"}) is None


def test_exige_a_chave(db_temporario, api_falsa, tmp_path):
    from avesrag_builder.core.settings import MissingSettingError

    with pytest.raises(MissingSettingError, match="EBIRD_API_KEY"):
        ebird.ingerir(db_temporario, piloto=True, settings=Settings(_env_file=None))
