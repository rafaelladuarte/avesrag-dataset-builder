"""
src/extractors/sibbr.py
Coleta registros do SiBBr (via dataset GBIF) para o PostGIS.
"""
from pymongo import database_shared
import requests
from src.extractors.base import BaseExtractor
from src.database.conexoes import DatabaseConnection

class SibbrExtractor(BaseExtractor):
    def __init__(self, limit=100):
        super().__init__()
        self.limit = limit
        self.base_url = "https://api.gbif.org/v1/occurrence/search"
        self.dataset_key = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
        self.db_connection = DatabaseConnection()

    def extract(self, nome_cientifico: str):
        resp = requests.get(
            self.base_url,
            params={
                "scientificName": nome_cientifico,
                "datasetKey": self.dataset_key,
                "country": "BR",
                "hasCoordinate": "true",
                "limit": self.limit,
            },
            timeout=30,
        )
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
                "nome_cientifico": nome_cientifico,
                "fonte": "sibbr",
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

    def load(self, transformed_data, db_connection):
        if not transformed_data:
            return
        db_connection.pg_insert_ocorrencias(transformed_data)

    def run_for_species(self, nome_cientifico: str, db_connection):
        raw = self.extract(nome_cientifico)
        clean = self.transform(raw, nome_cientifico)
        self.load(clean, db_connection)


if __name__ == "__main__":
    extractor = SibbrExtractor()
    extractor.run_for_species("Amazona aestiva", None)