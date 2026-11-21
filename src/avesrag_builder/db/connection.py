"""Conexão com o MongoDB.

Um único cliente por processo. A conexão não cria índices nem collections:
cada etapa do pipeline é responsável pelas suas.
"""

from pymongo import MongoClient
from pymongo.database import Database

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.settings import get_settings

logger = get_logger(__name__)

SERVER_SELECTION_TIMEOUT_MS = 5000

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Cliente MongoDB compartilhado, criado na primeira chamada."""
    global _client
    if _client is None:
        _client = MongoClient(
            get_settings().MONGODB_URI, serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS
        )
    return _client


def get_db() -> Database:
    """Banco configurado em MONGODB_DATABASE."""
    return get_client()[get_settings().MONGODB_DATABASE]


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
