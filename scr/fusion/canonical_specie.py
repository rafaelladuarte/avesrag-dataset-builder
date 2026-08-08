import csv
import re
from datetime import datetime, timezone
from uuid import uuid4

from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

from scr.core.config import settings
from scr.core.logging import get_logger

logger = get_logger(__name__)

# ===========================
# Configuração MongoDB
# ===========================

MONGO_URI = str(settings.MONGODB_URI)

DATABASE = settings.MONGODB_DATABASE

COLLECTION_WIKIAVES = "wikiaves"
COLLECTION_AVONET = "avonet"

COLLECTION_CANONICAL = "canonical_species"


# ==========================================================
# Utilidades
# ==========================================================


def get_size(text):
    """
    Extrai:
    Mede 8,6 centímetros
    """

    if not text:
        return {"min": None, "max": None}

    m = re.search(r"Mede\s+([\d,]+)\s+cent", text)

    if not m:
        return {"min": None, "max": None}

    value = float(m.group(1).replace(",", "."))

    return {"min": value, "max": value}


def get_weight(text):
    """
    Extrai:
    pesa de 1,8 a 2,2 gramas
    """

    if not text:
        return {"min": None, "max": None}

    m = re.search(r"pesa\s+de\s+([\d,]+)\s+a\s+([\d,]+)", text, flags=re.IGNORECASE)

    if not m:
        return {"min": None, "max": None}

    return {"min": float(m.group(1).replace(",", ".")), "max": float(m.group(2).replace(",", "."))}


# ==========================================================
# Merge
# ==========================================================


def main():
    client = MongoClient(MONGO_URI)

    db = client[DATABASE]

    wikiaves = db[COLLECTION_WIKIAVES]
    avonet = db[COLLECTION_AVONET]
    canonical = db[COLLECTION_CANONICAL]

    canonical.create_index("scientific_name", unique=True)

    CSV_PATH = "data/raw/wikiaves_especies.csv"

    operations = []

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scientific_name = row["nome_cientifico"]

            avo = avonet.find_one({"nome_cientifico": scientific_name}) or {}

            wiki = wikiaves.find_one({"nome_cientifico.nome": scientific_name})

            morphology_text = ""

            if wiki:
                morphology_text = wiki.get("caracteristicas", "")

            size = get_size(morphology_text)
            weight = get_weight(morphology_text)

            document = {
                "species_id": str(uuid4()),
                "scientific_name": scientific_name,
                "authority": (wiki.get("nome_cientifico", {}).get("autoridade") if wiki else None),
                "common_names": {
                    "pt": [wiki.get("meta_nome_comum")] if wiki else [],
                    "en": [wiki.get("nome_ingles")] if wiki else [],
                },
                "taxonomy": {
                    "kingdom": (
                        wiki.get("classificacao_cientifica", {}).get("Reino") if wiki else None
                    ),
                    "phylum": (
                        wiki.get("classificacao_cientifica", {}).get("Filo") if wiki else None
                    ),
                    "class": (
                        wiki.get("classificacao_cientifica", {}).get("Classe") if wiki else None
                    ),
                    "order": avo.get("ordem"),
                    "family": avo.get("familia"),
                    "genus": scientific_name.split()[0],
                    "species": scientific_name,
                },
                "morphology": {
                    "size_cm": size,
                    "weight_g": {
                        "min": weight["min"],
                        "max": weight["max"],
                        "mean": avo.get("massa_corporal_g"),
                    },
                    "colors": [],
                    "beak": {
                        "shape": "",
                        "culmen_mm": avo.get("bico_comprimento_culmen_mm"),
                        "nares_mm": avo.get("bico_comprimento_nares_mm"),
                        "width_mm": avo.get("bico_largura_mm"),
                        "depth_mm": avo.get("bico_profundidade_mm"),
                    },
                    "wing": {
                        "shape": "",
                        "length_mm": avo.get("asa_comprimento_mm"),
                        "hand_wing_index": avo.get("indice_asa_mao"),
                        "kipps_distance_mm": avo.get("kipps_distancia_mm"),
                    },
                    "tail": {"shape": "", "length_mm": avo.get("cauda_comprimento_mm")},
                    "tarsus_mm": avo.get("tarso_comprimento_mm"),
                    "sexual_dimorphism": "",
                    "juvenile_description": "",
                    "distinctive_features": [],
                },
                "description": {
                    "short": "",
                    "detailed": (wiki.get("caracteristicas") if wiki else ""),
                    "behavior": [],
                    "identification": "",
                },
                "diet": {
                    "guilds": [avo.get("nicho_trofico")] if avo.get("nicho_trofico") else [],
                    "food_items": [],
                },
                "habitat": {
                    "primary": [avo.get("habitat_avonet")] if avo.get("habitat_avonet") else [],
                    "secondary": [],
                    "altitude_range_m": {"min": None, "max": None},
                },
                "occurrence": {
                    "countries": [],
                    "states": [],
                    "municipalities": [],
                    "biomes": [],
                    "range_area_km2": avo.get("area_distribuicao_km2"),
                    "endemism": "",
                    "range_type": "",
                },
                "ecology": {
                    "activity_pattern": "",
                    "social_structure": "",
                    "migration": avo.get("migracao"),
                    "primary_lifestyle": avo.get("estilo_vida_primario"),
                    "trophic_level": avo.get("nivel_trofico"),
                    "trophic_niche": avo.get("nicho_trofico"),
                    "reproduction": "",
                },
                "conservation": {
                    "iucn_status": (wiki.get("estado_de_conservacao") if wiki else ""),
                    "population_trend": "",
                    "cites": "",
                },
                "external_ids": {
                    "wikiaves": (wiki.get("meta_id") if wiki else None),
                    "gbif": None,
                    "ebird": None,
                    "iucn": None,
                    "birdlife": None,
                },
                "data_quality": {
                    "confidence_score": None,
                    "sources": ["AVONET" if avo else None, "WikiAves" if wiki else None],
                    "schema_version": "1.0",
                    "pipeline_version": "1.0",
                    "last_updated": datetime.now(timezone.utc),
                },
            }

            document["data_quality"]["sources"] = [
                s for s in document["data_quality"]["sources"] if s
            ]

            operations.append(
                UpdateOne({"scientific_name": scientific_name}, {"$set": document}, upsert=True)
            )

    if operations:
        try:
            result = canonical.bulk_write(operations, ordered=False)
            logger.info(
                f"Canonical species criadas com sucesso: "
                f"{result.upserted_count} inseridas, {result.modified_count} atualizadas."
            )
        except BulkWriteError as e:
            logger.error(f"Erro no bulk_write: {e.details}")
    else:
        logger.warning("Nenhuma espécie para processar.")

    client.close()


if __name__ == "__main__":
    main()
