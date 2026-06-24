"""
src/database/conexoes.py
Gerencia conexões com MongoDB e PostGIS de forma estruturada.
"""
import os
import logging
import psycopg2
from pymongo import MongoClient
from contextlib import contextmanager
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """
    Classe para gerenciar conexões com MongoDB e PostgreSQL.
    """
    _mongo_client = None

    def __init__(self):
        # Configurações do PostgreSQL
        self.pg_uri = os.environ.get("POSTGRES_URI", "postgresql://aves:aves@localhost:5432/aves_brasil")
        
        # Configurações do MongoDB
        self.mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        self.mongo_db_name = "aves_brasil"

    @contextmanager
    def get_pg_connection(self):
        """
        Context Manager para conexão segura ao PostgreSQL.
        """
        conn = None
        try:
            conn = psycopg2.connect(self.pg_uri)
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Erro de conexão com PostgreSQL: {e}")
            raise
        finally:
            if conn is not None and not conn.closed:
                conn.close()

    def get_mongo_db(self):
        """
        Retorna e gerencia uma conexão reutilizável com o MongoDB.
        """
        if DatabaseConnection._mongo_client is None:
            DatabaseConnection._mongo_client = MongoClient(self.mongo_uri)
            db = DatabaseConnection._mongo_client[self.mongo_db_name]
            self._criar_indices_mongo(db)
        return DatabaseConnection._mongo_client[self.mongo_db_name]

    def _criar_indices_mongo(self, db):
        try:
            db.especies.create_index("nome_cientifico", unique=True)
            db.especies.create_index("familia")
            db.especies.create_index("ordem")
            db.especies.create_index("status_iucn")
            db.especies.create_index("fontes")
            logger.debug("Índices MongoDB verificados.")
        except Exception as e:
            logger.error(f"Erro ao criar índices no MongoDB: {e}")

    def pg_insert_ocorrencias(self, registros: list[dict]):
        """
        Insere ocorrências em lote no PostGIS.
        """
        if not registros:
            return

        rows = [
            (
                r["nome_cientifico"],
                r["fonte"],
                r.get("fonte_id"),
                r.get("data_observacao"),
                r.get("municipio"),
                r.get("estado"),
                r.get("altitude_m"),
                r.get("instituicao"),
                r["longitude"],
                r["latitude"],
            )
            for r in registros
            if r.get("longitude") and r.get("latitude")
        ]

        if not rows:
            return

        sql = """
            INSERT INTO ocorrencias
                (nome_cientifico, fonte, fonte_id, data_observacao,
                 municipio, estado, altitude_m, instituicao, geom)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        template = """(
            %s, %s, %s, %s, %s, %s, %s, %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        )"""

        with self.get_pg_connection() as conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, rows, template=template)
            conn.commit()
        logger.info(f"PostGIS: {len(rows)} ocorrências inseridas.")
