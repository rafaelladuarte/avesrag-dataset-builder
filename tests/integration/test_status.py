"""Integração: `status` lê o banco sem gravar nada (pytest -m integration)."""

import pytest

from avesrag_builder.db.collections import RAW_CBRO, RAW_EBIRD, SPECIES_REGISTRY
from avesrag_builder.status import coletar, proximo_passo

pytestmark = pytest.mark.integration

PILOTO = "3170206"


def test_banco_vazio_comeca_pela_ingestao(db_temporario):
    e = coletar(db_temporario, piloto=True, geocodigo=PILOTO)
    assert e.registry == 0
    assert proximo_passo(e) == "ingest cbro"
    assert db_temporario.list_collection_names() == []  # não criou nada


def test_registry_sem_o_municipio_do_piloto(db_temporario):
    db = db_temporario
    for col in (RAW_CBRO, "raw_ibge", "raw_birdbase", "raw_avonet", "raw_birdalbum"):
        db[col].insert_one({"_id": "x", "dados": {}})
    db["raw_wikiaves"].insert_one({"_id": "1", "dados": {"lista": {}, "pagina": {}}})
    db[SPECIES_REGISTRY].insert_one({"species_id": "sp_a_b", "chaves": {"wikiaves": "1"}})
    e = coletar(db, piloto=True, geocodigo=PILOTO)
    assert e.escopo == 0  # sem raw_ebird do município, o piloto fica vazio
    assert proximo_passo(e) == "ingest ebird --piloto"

    db[RAW_EBIRD].insert_one({"_id": f"municipio:{PILOTO}", "dados": {"especies": []}})
    e = coletar(db, piloto=False, geocodigo=PILOTO)
    assert (e.escopo, e.escopo_com_pagina) == (1, 1)
    assert proximo_passo(e) == "ingest commons"  # as fotos partem do registry

    db["raw_commons"].insert_one({"_id": "wikidata:Q1", "dados": {}})
    assert proximo_passo(coletar(db, piloto=False, geocodigo=PILOTO)) == "ingest inaturalist"

    db["raw_inaturalist"].insert_one({"_id": "taxon:1", "dados": {}})
    assert proximo_passo(coletar(db, piloto=False, geocodigo=PILOTO)) == "extract"
