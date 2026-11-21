"""Nomes das collections do builder (Modelo de Dados > Documentos)."""

RAW_WIKIAVES = "raw_wikiaves"
RAW_AVONET = "raw_avonet"
RAW_BIRDBASE = "raw_birdbase"
RAW_CBRO = "raw_cbro"
RAW_EBIRD = "raw_ebird"
RAW_IBGE = "raw_ibge"

SPECIES_REGISTRY = "species_registry"
SPECIES_EXTRACTIONS = "species_extractions"
SPECIES_OCCURRENCE = "species_occurrence"
SPECIES = "species"
SPECIES_RETRIEVAL_DOCS = "species_retrieval_docs"

RAW_COLLECTIONS = (RAW_WIKIAVES, RAW_AVONET, RAW_BIRDBASE, RAW_CBRO, RAW_EBIRD, RAW_IBGE)

# Escritas pelo builder, na ordem do pipeline.
BUILDER_COLLECTIONS = (
    *RAW_COLLECTIONS,
    SPECIES_REGISTRY,
    SPECIES_EXTRACTIONS,
    SPECIES_OCCURRENCE,
    SPECIES,
    SPECIES_RETRIEVAL_DOCS,
)
