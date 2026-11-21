"""Conexão com o MongoDB.

Um único cliente por processo. A conexão não cria índices nem collections:
cada etapa do pipeline é responsável pelas suas.
"""

from pymongo import MongoClient

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.settings import get_settings

logger = get_logger(__name__)


class DatabaseConnection:
    """Gerencia um cliente MongoDB reutilizável."""

    _mongo_client = None

    def __init__(self):
        settings = get_settings()
        self.mongo_uri = settings.MONGODB_URI
        self.mongo_db_name = settings.MONGODB_DATABASE

    def get_mongo_db(self):
        """Retorna o banco configurado, criando o cliente na primeira chamada."""
        if DatabaseConnection._mongo_client is None:
            DatabaseConnection._mongo_client = MongoClient(self.mongo_uri)
        return DatabaseConnection._mongo_client[self.mongo_db_name]
