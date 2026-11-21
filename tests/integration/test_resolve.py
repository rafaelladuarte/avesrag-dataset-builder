"""Integração: `resolve` grava species_registry e relatórios (pytest -m integration)."""

import pytest

from avesrag_builder.core.models import RawEnvelope
from avesrag_builder.core.settings import get_settings
from avesrag_builder.db.collections import (
    RAW_BIRDBASE,
    RAW_CBRO,
    RAW_EBIRD,
    RAW_WIKIAVES,
    SPECIES_REGISTRY,
)
from avesrag_builder.resolve.registry import especies_do_piloto, executar

pytestmark = pytest.mark.integration

GEOCODIGO = "3170206"


def _wiki(id_, nome, familia):
    return {
        "lista": {
            "id": id_,
            "nome_cientifico": nome,
            "nome_comum": nome.lower(),
            "familia": familia,
        }
    }


def _taxon(codigo, nome, familia):
    return {
        "sciName": nome,
        "speciesCode": codigo,
        "category": "species",
        "familySciName": familia,
        "comName": nome,
    }


@pytest.fixture
def db(db_temporario):
    raw = {
        RAW_WIKIAVES: [
            ("1", _wiki("1", "Pitangus sulphuratus", "Tyrannidae")),
            ("2", _wiki("2", "Avis inexistens", "Tyrannidae")),
        ],
        RAW_CBRO: [("CBRO#1", {"Nome do táxon (sem autoria)": "Pitangus sulphuratus"})],
        RAW_EBIRD: [
            ("taxon:grekis", _taxon("grekis", "Pitangus sulphuratus", "Tyrannidae")),
            ("taxon:redjun", _taxon("redjun", "Gallus gallus", "Phasianidae")),
            ("municipio:" + GEOCODIGO, {"especies": ["grekis", "redjun"]}),
        ],
    }
    for nome, regs in raw.items():
        db_temporario[nome].insert_many([RawEnvelope.build(i, d).to_mongo() for i, d in regs])
    return db_temporario


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    monkeypatch.setenv("PILOTO_MUNICIPIO_IBGE", GEOCODIGO)
    get_settings.cache_clear()
    s = get_settings()
    assert s.REPORTS_DIR == tmp_path
    return s


def test_duas_execucoes(db, settings):
    r1, cob = executar(db, settings)
    assert (r1.inseridos, r1.atualizados) == (2, 0)
    antes = {d["species_id"]: (d["_id"], d["criado_em"]) for d in db[SPECIES_REGISTRY].find()}

    r2, _ = executar(db, settings)
    assert (r2.inseridos, r2.atualizados, r2.inalterados) == (0, 0, 2)
    depois = {d["species_id"]: (d["_id"], d["criado_em"]) for d in db[SPECIES_REGISTRY].find()}
    assert antes == depois

    assert (cob.piloto_no_registry, cob.piloto_codigos) == (1, 2)
    assert especies_do_piloto(db, GEOCODIGO) == ["sp_pitangus_sulphuratus"]


def test_atualiza_quando_a_fonte_muda_e_mantem_criado_em(db, settings):
    executar(db, settings)
    criado = db[SPECIES_REGISTRY].find_one({"species_id": "sp_avis_inexistens"})["criado_em"]
    db[RAW_CBRO].insert_one(
        RawEnvelope.build("CBRO#2", {"Nome do táxon (sem autoria)": "Avis inexistens"}).to_mongo()
    )

    r, _ = executar(db, settings)
    assert r.atualizados == 1
    doc = db[SPECIES_REGISTRY].find_one({"species_id": "sp_avis_inexistens"})
    assert doc["chaves"]["cbro"] == "CBRO#2" and doc["match"]["cbro"] == "exato"
    assert doc["criado_em"] == criado


def test_orfao_nao_e_apagado(db, settings):
    executar(db, settings)
    db[RAW_WIKIAVES].delete_one({"_id": "2"})
    r, _ = executar(db, settings)
    assert r.ausentes_na_fonte == 1
    assert db[SPECIES_REGISTRY].count_documents({}) == 2
    assert (settings.REPORTS_DIR / "resolve_orfaos.txt").read_text() == "sp_avis_inexistens\n"


def test_relatorios(db, settings):
    executar(db, settings)
    sem_match = (settings.REPORTS_DIR / "resolve_sem_match.tsv").read_text().splitlines()
    assert "cbro\tsp_avis_inexistens\tAvis inexistens" in sem_match
    piloto = (settings.REPORTS_DIR / "resolve_piloto.tsv").read_text().splitlines()
    assert piloto[1].split("\t")[:4] == [
        "redjun",
        "Gallus gallus",
        "Gallus gallus",
        "domestica_exotica",
    ]


def test_birdbase_com_ponto_no_nome_da_coluna(db, settings):
    # "HBW/BirdLife International (v9.1)": uma projeção "dados.<coluna>" não acharia o campo.
    db[RAW_BIRDBASE].insert_one(
        RawEnvelope.build(
            "777", {"HBW/BirdLife International (v9.1)": "Avis inexistens"}
        ).to_mongo()
    )
    executar(db, settings)
    doc = db[SPECIES_REGISTRY].find_one({"species_id": "sp_avis_inexistens"})
    assert doc["chaves"]["birdbase"] == "777"
