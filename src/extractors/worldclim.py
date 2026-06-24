"""
src/extractors/worldclim.py
Extrai variáveis bioclimáticas WorldClim nas coordenadas
de ocorrência de cada espécie e persiste no MongoDB.
"""
import os
import numpy as np
from src.extractors.base import BaseExtractor

BIOCLIM = {
    "bio1": ("temp_media_anual_c", 10.0),
    "bio7": ("amplitude_termica_anual_c", 10.0),
    "bio12": ("precipitacao_anual_mm", 1.0),
    "bio15": ("sazonalidade_precipitacao", 1.0),
}

class WorldclimExtractor(BaseExtractor):
    def __init__(self):
        super().__init__()
        self.wc_dir = os.environ.get("WORLDCLIM_DIR", "dados/worldclim/")

    def extract(self, nome_cientifico: str, db_connection):
        if not os.path.isdir(self.wc_dir):
            self.logger.warning(f"Diretório WorldClim não encontrado: {self.wc_dir}")
            return []

        with db_connection.get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ST_X(geom) AS lon, ST_Y(geom) AS lat
                    FROM ocorrencias
                    WHERE nome_cientifico = %s
                      AND geom IS NOT NULL
                    LIMIT 500
                """, (nome_cientifico,))
                coords = cur.fetchall()

        return coords

    def transform(self, raw_data):
        if not raw_data:
            return {}

        try:
            import rasterio
        except ImportError:
            self.logger.warning("rasterio não instalado — pulando WorldClim transform.")
            return {}

        coords = raw_data
        clima = {}
        for var_arq, (var_nome, escala) in BIOCLIM.items():
            tif = os.path.join(self.wc_dir, f"wc2.1_30s_{var_arq}.tif")
            if not os.path.exists(tif):
                continue
            with rasterio.open(tif) as src:
                vals = []
                for lon, lat in coords:
                    try:
                        row, col = src.index(lon, lat)
                        v = src.read(1)[row, col]
                        if v != src.nodata:
                            vals.append(float(v) / escala)
                    except Exception:
                        pass
                if vals:
                    clima[f"wc_{var_nome}_media"] = round(float(np.mean(vals)), 2)
                    clima[f"wc_{var_nome}_dp"] = round(float(np.std(vals)), 2)
        return clima

    def load(self, transformed_data, db_connection, nome_cientifico: str = None):
        if not transformed_data or not nome_cientifico:
            return

        db = db_connection.get_mongo_db()
        db.especies.update_one(
            {"nome_cientifico": nome_cientifico},
            {"$set": transformed_data, "$addToSet": {"fontes": "worldclim"}},
        )

    def run_for_species(self, nome_cientifico: str, db_connection):
        raw = self.extract(nome_cientifico, db_connection)
        clean = self.transform(raw)
        self.load(clean, db_connection, nome_cientifico)
