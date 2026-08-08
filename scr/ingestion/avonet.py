import os
import pandas as pd
from datetime import datetime
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from scr.ingestion.base import BaseExtractor
from scr.database.connection import DatabaseConnection

COLUNAS = {
    "Species1": "nome_cientifico",
    "Family1": "familia",
    "Order1": "ordem",
    "Beak.Length_Culmen": "bico_comprimento_culmen_mm",
    "Beak.Length_Nares": "bico_comprimento_nares_mm",
    "Beak.Width": "bico_largura_mm",
    "Beak.Depth": "bico_profundidade_mm",
    "Tarsus.Length": "tarso_comprimento_mm",
    "Wing.Length": "asa_comprimento_mm",
    "Kipps.Distance": "kipps_distancia_mm",
    "Secondary1": "secundaria1_mm",
    "Hand-Wing.Index": "indice_asa_mao",
    "Tail.Length": "cauda_comprimento_mm",
    "Mass": "massa_corporal_g",
    "Habitat": "habitat_avonet",
    "Trophic.Level": "nivel_trofico",
    "Trophic.Niche": "nicho_trofico",
    "Primary.Lifestyle": "estilo_vida_primario",
    "Migration": "migracao",
    "Range.Size": "area_distribuicao_km2",
}

class AvonetIngestion(BaseExtractor):
    def __init__(self):
        super().__init__()
        self.csv_path = os.environ.get("AVONET_CSV", "data/AVONET_BirdLife.xlsx")
        self.db_connection = DatabaseConnection()

    def extract(self):
        if not os.path.exists(self.csv_path):
            self.logger.error(f"AVONET arquivo não encontrado: {self.csv_path}")
            return pd.DataFrame()

        if self.csv_path.lower().endswith('.xlsx'):
            return pd.read_excel(self.csv_path, sheet_name='AVONET1_BirdLife')
        else:
            return pd.read_csv(self.csv_path, encoding="utf-8")

    def transform(self, raw_data, especies_alvo: set = None):
        if raw_data.empty:
            return []

        df = raw_data.rename(columns=COLUNAS)[list(COLUNAS.values())]

        if especies_alvo:
            df = df[df["nome_cientifico"].isin(especies_alvo)]
            self.logger.info(f"AVONET: filtrando {len(especies_alvo)} espécies-alvo")

        docs = []
        for _, row in df.iterrows():
            doc = row.dropna().to_dict()
            doc["fontes"] = ["avonet"]
            doc["atualizado_em"] = datetime.now()
            docs.append(doc)
        return docs

    def load(self, transformed_data, db_connection=None):
        if not transformed_data:
            return set()

        db = self.db_connection.get_mongo_db()
        
        ops = []
        carregadas = set()

        for doc in transformed_data:
            carregadas.add(doc["nome_cientifico"])
            ops.append(UpdateOne(
                {"nome_cientifico": doc["nome_cientifico"]},
                {"$set": doc},
                upsert=True,
            ))

        if ops:
            try:
                db.avonet.bulk_write(ops, ordered=False)
                self.logger.info(f"AVONET: {len(ops)} espécies carregadas na collection 'avonet' do MongoDB (banco 'avesrag').")
            except BulkWriteError as e:
                self.logger.error(f"AVONET bulk_write error: {e.details}")

        return carregadas

    def run(self, db_connection=None, especies_alvo: set = None):
        self.logger.info("Iniciando processo de Extração AVONET...")
        raw_data = self.extract()
        
        self.logger.info("Iniciando processo de Transformação...")
        clean_data = self.transform(raw_data, especies_alvo)
        
        self.logger.info("Iniciando processo de Carga (Load)...")
        carregadas = self.load(clean_data)
        
        return carregadas


if __name__ == "__main__":
    extractor = AvonetIngestion()
    extractor.run()