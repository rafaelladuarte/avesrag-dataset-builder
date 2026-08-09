from pymongo import MongoClient

from scr.core.config import settings
from scr.core.logging import get_logger

logger = get_logger(__name__)


def main():
    """Reseta o flag _pipeline_processed para reprocessar documentos com o novo schema."""
    logger.info("Iniciando reset do pipeline...")
    client = MongoClient(str(settings.MONGODB_URI))
    db = client[settings.MONGODB_DATABASE]

    # Conta documentos já processados
    count = db.wikiaves.count_documents({"_pipeline_processed": True})
    logger.info(f"Encontrados {count} documentos já processados.")

    if count == 0:
        logger.info("Nenhum documento para resetar.")
        return

    # Remove o flag e as camadas antigas
    result = db.wikiaves.update_many(
        {"_pipeline_processed": True},
        {
            "$unset": {
                "_pipeline_processed": "",
                "species_raw": "",
                "species_normalized": "",
                "canonical_species": "",
            }
        },
    )
    logger.info(f"Reset concluído: {result.modified_count} documentos atualizados.")


if __name__ == "__main__":
    main()
