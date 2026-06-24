"""
src/extractors/ebird.py
Coleta checklists de espécies por estado via API eBird.
"""
import os
import requests
from src.extractors.base import BaseExtractor
from src.database.conexoes import DatabaseConnection

ESTADOS_BR = [
    "BR-AC","BR-AL","BR-AP","BR-AM","BR-BA","BR-CE","BR-DF",
    "BR-ES","BR-GO","BR-MA","BR-MT","BR-MS","BR-MG","BR-PA",
    "BR-PB","BR-PR","BR-PE","BR-PI","BR-RJ","BR-RN","BR-RS",
    "BR-RO","BR-RR","BR-SC","BR-SP","BR-SE","BR-TO",
]

class EbirdExtractor(BaseExtractor):
    def __init__(self):
        super().__init__()
        self.db_connection = DatabaseConnection()
        self.token = os.environ.get("EBIRD_TOKEN", "")

    def extract(self, estados: list = None):
        if not self.token:
            self.logger.warning("EBIRD_TOKEN não configurado.")
            return {}

        headers = {"X-eBirdApiToken": self.token}
        alvos = estados or ESTADOS_BR
        resultados_estado = {}

        for estado in alvos:
            url = f"https://api.ebird.org/v2/product/spplist/{estado}"
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                continue

            codigos = resp.json()
            resultados_estado[estado] = codigos
            self.logger.info(f"eBird: checklist do estado {estado} extraído.")
        
        return resultados_estado

    def transform(self, raw_data):
        if not raw_data:
            return []

        headers = {"X-eBirdApiToken": self.token}
        docs = []

        for estado, codigos in raw_data.items():
            for codigo in codigos:
                r2 = requests.get(
                    f"https://api.ebird.org/v2/ref/taxonomy/ebird",
                    params={"species": codigo, "fmt": "json"},
                    headers=headers, timeout=10,
                )
                if r2.status_code == 200 and r2.json():
                    nome = r2.json()[0].get("sciName", "")
                    if nome:
                        docs.append({
                            "nome_cientifico": nome,
                            "ebird_codigo": codigo,
                            "estado_sigla": estado[-2:],
                        })
        return docs

    def load(self, transformed_data):
        if not transformed_data:
            return

        db = self.db_connection.get_mongo_db()
        for doc in transformed_data:
            db.especies.update_one(
                {"nome_cientifico": doc["nome_cientifico"]},
                {
                    "$addToSet": {"fontes": "ebird"},
                    "$set": {
                        "ebird_codigo": doc["ebird_codigo"],
                        f"ebird_estados.{doc['estado_sigla']}": True,
                    },
                },
            )
        self.logger.info("eBird: carregamento no MongoDB concluído.")
