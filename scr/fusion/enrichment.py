import logging

from pymongo import MongoClient

from scr.core.config import settings
from scr.llm.pipeline import EnrichmentPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("Iniciando pipeline de enriquecimento...")
    client = MongoClient(str(settings.MONGODB_URI))
    db = client[settings.MONGODB_DATABASE]

    # Instancia o pipeline (que usará o Gemini)
    pipeline = EnrichmentPipeline()

    # Busca até 5 espécies que ainda não foram processadas
    docs = db.wikiaves.find({"_pipeline_processed": {"$ne": True}}).limit(5)

    for doc in docs:
        nome = doc.get("nome_cientifico", {}).get("nome", "Desconhecido")
        logger.info(f"Processando espécie: {nome}")

        try:
            # Roda o pipeline de enriquecimento
            enriched_data = pipeline.process_species(doc)

            # Atualiza o banco com a nova camada
            db.wikiaves.update_one(
                {"_id": doc["_id"]},
                {"$set": {"species_raw": enriched_data, "_pipeline_processed": True}},
            )
            logger.info(f"✅ Sucesso para: {nome}")
        except Exception as e:
            logger.error(f"❌ Erro ao processar {nome}: {e}")


if __name__ == "__main__":
    main()
