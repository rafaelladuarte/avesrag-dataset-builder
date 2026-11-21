import uuid

import pytest
from pymongo.errors import PyMongoError

from avesrag_builder.db import connection


@pytest.fixture
def db_temporario():
    """Banco descartável no MongoDB de MONGODB_URI; pula se o servidor não responder."""
    connection.close()
    try:
        client = connection.get_client()
        client.admin.command("ping")
    except PyMongoError as e:
        pytest.skip(f"MongoDB indisponível em MONGODB_URI: {e}")
    nome = f"avesrag_teste_{uuid.uuid4().hex[:8]}"
    yield client[nome]
    client.drop_database(nome)
    connection.close()
