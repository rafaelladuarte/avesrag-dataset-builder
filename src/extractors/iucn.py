"""
src/extractors/iucn.py
Enriquece espécies com status de conservação da IUCN Red List.
"""
import os
import requests
from src.extractors.base import BaseExtractor
from src.database.conexoes import DatabaseConnection

class IUCNExtractor(BaseExtractor):
    def __init__(self):
        super().__init__()
        self.base_url = "https://apiv4.iucnredlist.org/api/v4"
        self.token = os.environ.get("IUCN_TOKEN", "")
        self.db_connection = DatabaseConnection()

    def extract(self, nome_cientifico: str):
        if not self.token:
            self.logger.warning("IUCN_TOKEN não configurado.")
            return None

        partes = nome_cientifico.split()
        if len(partes) < 2:
            return None

        resp = requests.get(
            f"{self.base_url}/taxa/scientific_name",
            params={"genus_name": partes[0], "species_name": partes[1]},
            headers={"Authorization": f"Token {self.token}"},
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        avaliacoes = resp.json().get("assessments", [])
        return avaliacoes[0] if avaliacoes else None

    def transform(self, raw_data, nome_cientifico: str = None):
        if not raw_data:
            return None

        return {
            "nome_cientifico": nome_cientifico,
            "status_iucn": raw_data.get("red_list_category", {}).get("code"),
            "status_iucn_descricao": raw_data.get("red_list_category", {}).get("name"),
            "iucn_id": raw_data.get("taxon_id"),
            "ano_avaliacao_iucn": raw_data.get("year_published"),
        }

    def load(self, transformed_data):
        if not transformed_data:
            return

        db = self.db_connection.get_mongo_db()
        nome_cientifico = transformed_data.pop("nome_cientifico")
        
        db.especies.update_one(
            {"nome_cientifico": nome_cientifico},
            {
                "$set": transformed_data,
                "$addToSet": {"fontes": "iucn"},
            },
        )

    def run_for_species(self, nome_cientifico: str):
        raw = self.extract(nome_cientifico)
        clean = self.transform(raw, nome_cientifico)
        self.load(clean)
