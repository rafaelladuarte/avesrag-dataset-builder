"""Integração: ponte de nomes do BIRDBASE usada pelo `ingest wikiaves --piloto`."""

import pytest

from avesrag_builder.core.models import RawEnvelope
from avesrag_builder.db.collections import RAW_BIRDBASE
from avesrag_builder.ingest.wikiaves import ponte_birdbase

pytestmark = pytest.mark.integration


def test_le_colunas_com_ponto_no_nome(db_temporario):
    # "(v9.1)" e "(v15.1)": uma projeção "dados.<coluna>" não acharia esses campos.
    dados = {
        "eBird/Clements (V2024b)": "Buteogallus urubitinga",
        "HBW/BirdLife International (v9.1)": "Urubitinga urubitinga",
        "IOC World Bird List (v15.1)": "Buteogallus urubitinga",
    }
    db_temporario[RAW_BIRDBASE].insert_one(RawEnvelope.build("1", dados).to_mongo())
    assert ponte_birdbase(db_temporario) == {
        "Buteogallus urubitinga": {"Urubitinga urubitinga", "Buteogallus urubitinga"}
    }
