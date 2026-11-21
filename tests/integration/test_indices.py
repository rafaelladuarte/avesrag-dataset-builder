"""Integração: índice único de species_id (pytest -m integration)."""

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from avesrag_builder.db.collections import POR_ESPECIE, SPECIES_REGISTRY, garantir_indices

pytestmark = pytest.mark.integration


def test_indice_unico_criado_e_idempotente(db_temporario):
    garantir_indices(db_temporario)
    garantir_indices(db_temporario)
    for nome in POR_ESPECIE:
        info = db_temporario[nome].index_information()["species_id_unico"]
        assert info["unique"] is True


def test_upsert_pelo_species_id_nao_duplica(db_temporario):
    garantir_indices(db_temporario)
    col = db_temporario[SPECIES_REGISTRY]
    slug = "sp_pitangus_sulphuratus"
    for _ in range(2):
        col.update_one(
            {"species_id": slug},
            {"$setOnInsert": {"species_id": slug}, "$set": {"nome_comum": "bem-te-vi"}},
            upsert=True,
        )
    docs = list(col.find({"species_id": slug}))
    assert len(docs) == 1
    assert isinstance(docs[0]["_id"], ObjectId)

    with pytest.raises(DuplicateKeyError):
        col.insert_one({"species_id": slug})
