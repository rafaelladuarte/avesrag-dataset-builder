"""Integração: o MongoDB de MONGODB_URI aceita índices $vectorSearch e $search.

Roda com `pytest -m integration` e o docker-compose de pé. É pulado se o
servidor não responder.
"""

import pytest
from pymongo.errors import PyMongoError

from avesrag_builder.db import connection
from avesrag_builder.db.busca import PREFIXO_COLLECTION, verificar_busca

pytestmark = pytest.mark.integration


@pytest.fixture
def db():
    connection.close()
    try:
        banco = connection.get_db()
        banco.client.admin.command("ping")
    except PyMongoError as e:
        pytest.skip(f"MongoDB indisponível em MONGODB_URI: {e}")
    yield banco
    connection.close()


def test_aceita_indices_de_busca(db):
    resultado = verificar_busca(db)
    assert resultado.vector_search == ["a", "c"]
    assert resultado.text_search[0] == "c"


def test_nao_deixa_collection_temporaria(db):
    verificar_busca(db)
    assert not [n for n in db.list_collection_names() if n.startswith(PREFIXO_COLLECTION)]
