"""
src/extractors/gbif.py
Coleta espécies e ocorrências de aves no Brasil via API GBIF.
"""
import time
import requests
import pandas as pd
from src.extractors.base import BaseExtractor
from src.database.conexoes import DatabaseConnection

class GBIFExtractor(BaseExtractor):
    """
    Coleta ocorrências georreferenciadas de uma espécie no Brasil
    e persiste no PostGIS.
    """
    def __init__(self, limit=200):
        super().__init__()
        self.limit = limit
        self.base_url = "https://api.gbif.org/v1/occurrence/search"
        self.classe_aves = 212
        self.db_connection = DatabaseConnection()

    def buscar_especies_brasil(self, limite_total: int = 10000) -> set:
        """
        Retorna set de nomes científicos de aves com ocorrência confirmada.
        """
        offset = 0
        limite_req = 300
        total = None
        especies = set()

        params = {
            "classKey": self.classe_aves,
            "country": "BR",
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",
            "limit": limite_req,
        }

        self.logger.info("GBIF: buscando espécies de aves no Brasil...")
        while total is None or offset < min(total, limite_total):
            params["offset"] = offset
            resp = requests.get(self.base_url, params=params, timeout=30)
            if resp.status_code != 200:
                self.logger.error(f"GBIF erro HTTP {resp.status_code}")
                break
            data = resp.json()
            total = data.get("count", 0)
            for rec in data.get("results", []):
                nome = rec.get("species") or rec.get("scientificName", "")
                if nome:
                    especies.add(nome.strip())
            offset += limite_req
            time.sleep(0.3)

        self.logger.info(f"GBIF: {len(especies)} espécies encontradas no Brasil.")
        return especies

    def extract(self, nome_cientifico: str, estado: str = None):
        params = {
            "scientificName": nome_cientifico,
            "country": "BR",
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",
            "limit": self.limit,
        }
        if estado:
            params["stateProvince"] = estado

        resp = requests.get(self.base_url, params=params, timeout=30)
        if resp.status_code != 200:
            return []

        return resp.json().get("results", [])

    def transform(self, raw_data, nome_cientifico: str = None):
        registros = []
        for rec in raw_data:
            lat = rec.get("decimalLatitude")
            lon = rec.get("decimalLongitude")
            if lat is None or lon is None:
                continue
            registros.append({
                "nome_cientifico": nome_cientifico or rec.get("scientificName", "Unknown"),
                "fonte": "gbif",
                "fonte_id": str(rec.get("key", "")),
                "data_observacao": rec.get("eventDate"),
                "municipio": rec.get("municipality"),
                "estado": rec.get("stateProvince", "")[:2] if rec.get("stateProvince") else None,
                "altitude_m": rec.get("elevation"),
                "instituicao": rec.get("institutionCode"),
                "latitude": lat,
                "longitude": lon,
            })
        return registros

    def load(self, transformed_data):
        if not transformed_data:
            self.logger.info("Nenhum dado transformado para carregar.")
            return
        self.db_connection.pg_insert_ocorrencias(transformed_data)
        self.logger.info(f"{len(transformed_data)} registros carregados via db_connection.")

    def run_for_species(self, nome_cientifico: str, db_connection):
        """Wrapper específico para rodar por espécie"""
        self.logger.info(f"Iniciando coleta para {nome_cientifico}")
        raw = self.extract(nome_cientifico)
        clean = self.transform(raw, nome_cientifico)
        self.load(clean, db_connection)
