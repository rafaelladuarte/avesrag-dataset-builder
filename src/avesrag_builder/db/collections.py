"""Nomes das collections do builder (Modelo de Dados > Documentos)."""

from pymongo import ASCENDING
from pymongo.database import Database

RAW_WIKIAVES = "raw_wikiaves"
RAW_AVONET = "raw_avonet"
RAW_BIRDBASE = "raw_birdbase"
RAW_CBRO = "raw_cbro"
RAW_EBIRD = "raw_ebird"
RAW_IBGE = "raw_ibge"
RAW_BIRDALBUM = "raw_birdalbum"
RAW_COMMONS = "raw_commons"
RAW_INATURALIST = "raw_inaturalist"

SPECIES_REGISTRY = "species_registry"
SPECIES_EXTRACTIONS = "species_extractions"
SPECIES_OCCURRENCE = "species_occurrence"
SPECIES = "species"
SPECIES_RETRIEVAL_DOCS = "species_retrieval_docs"

# Operacional: lotes enviados à API de batch do LLM, para retomar o `extract`.
LLM_BATCHES = "llm_batches"

RAW_COLLECTIONS = (
    RAW_WIKIAVES,
    RAW_AVONET,
    RAW_BIRDBASE,
    RAW_CBRO,
    RAW_EBIRD,
    RAW_IBGE,
    RAW_BIRDALBUM,
    RAW_COMMONS,
    RAW_INATURALIST,
)

# Escritas pelo builder, na ordem do pipeline.
BUILDER_COLLECTIONS = (
    *RAW_COLLECTIONS,
    SPECIES_REGISTRY,
    SPECIES_EXTRACTIONS,
    SPECIES_OCCURRENCE,
    SPECIES,
    SPECIES_RETRIEVAL_DOCS,
)

# Collections com um doc por espécie: `_id` é ObjectId e o slug fica em `species_id`.
POR_ESPECIE = (SPECIES_REGISTRY, SPECIES_OCCURRENCE, SPECIES)


def garantir_indices(db: Database) -> None:
    """Índice único em `species_id` nas collections por espécie (idempotente).

    Chamado pelo `resolve` e pelo `fuse` antes de gravar: sem ele, dois upserts
    pelo mesmo `species_id` poderiam criar documentos duplicados.
    """
    for nome in POR_ESPECIE:
        db[nome].create_index([("species_id", ASCENDING)], unique=True, name="species_id_unico")
