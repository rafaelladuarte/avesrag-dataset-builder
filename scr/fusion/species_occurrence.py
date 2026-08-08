import logging
import sys

from pymongo import MongoClient, UpdateOne

from scr.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ─── Configuração ────────────────────────────────────────────────────────────

MONGO_URI = str(settings.MONGODB_URI)
DATABASE = settings.MONGODB_DATABASE
SOURCE_COLLECTION = "ebird"
TARGET_COLLECTION = "ocorrencias_especies"

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _add_unique(lst: list, value: str) -> None:
    """Adiciona valor à lista apenas se ainda não existir (ordem de inserção)."""
    if value and value not in lst:
        lst.append(value)


# ─── Etapa 1: Extração e transformação em memória ────────────────────────────


def extrair_e_transformar(source_col) -> dict:
    """
    Lê todos os documentos da collection ebird e agrupa por espécie.
    Retorna dict keyed por speciesCode.
    Determinístico: mesma entrada → mesmo resultado.
    """
    especies: dict[str, dict] = {}

    total_docs = source_col.count_documents({})
    log.info("Lendo %d documentos de '%s'...", total_docs, SOURCE_COLLECTION)

    cursor = source_col.find(
        {},
        {
            "geocodigo": 1,
            "nome": 1,
            "uf": 1,
            "bioma": 1,
            "especies": 1,
        },
    ).sort("geocodigo", 1)  # ordenação garante determinismo

    for doc in cursor:
        municipio = doc.get("nome", "")
        uf = doc.get("uf", "")
        bioma = doc.get("bioma", "")
        geocodigo = doc.get("geocodigo", "")

        for sp in doc.get("especies", []):
            code = sp.get("speciesCode")
            if not code:
                continue

            if code not in especies:
                especies[code] = {
                    "nome_cientifico": sp.get("sciName", ""),
                    # listas ordenadas (inserção determinística via sort do cursor)
                    "paises": ["Brasil"],  # fonte é 100% BR
                    "estados": [],
                    "municipios": [],  # lista de objetos {geocodigo, nome, uf}
                    "biomas": [],
                    "contagem_ocorrencias": 0,
                }

            entry = especies[code]

            # estados
            _add_unique(entry["estados"], uf)

            # municípios (objeto compacto, deduplicado por geocodigo)
            mun_obj = {"geocodigo": geocodigo, "nome": municipio, "uf": uf}
            if mun_obj not in entry["municipios"]:
                entry["municipios"].append(mun_obj)

            # biomas
            _add_unique(entry["biomas"], bioma)

            # contagem = número de municípios onde ocorre
            entry["contagem_ocorrencias"] += 1

    log.info("Espécies únicas encontradas: %d", len(especies))
    return especies


# ─── Etapa 2: Carga (upsert determinístico) ──────────────────────────────────


def carregar(target_col, especies: dict) -> None:
    """
    Faz upsert em lote usando speciesCode como chave natural.
    Idempotente: rodar N vezes produz o mesmo resultado final.
    """
    if not especies:
        log.warning("Nenhuma espécie para carregar.")
        return

    BATCH = 500
    ops = []

    for doc in sorted(especies.values(), key=lambda x: x["nome_cientifico"]):
        ops.append(
            UpdateOne(
                {"nome_cientifico": doc["nome_cientifico"]},  # filtro (chave natural)
                {"$set": doc},  # substitui campos
                upsert=True,
            )
        )

        if len(ops) >= BATCH:
            result = target_col.bulk_write(ops, ordered=False)
            log.info(
                "Lote gravado — upserted: %d, modified: %d",
                result.upserted_count,
                result.modified_count,
            )
            ops = []

    if ops:
        result = target_col.bulk_write(ops, ordered=False)
        log.info(
            "Lote final — upserted: %d, modified: %d",
            result.upserted_count,
            result.modified_count,
        )


# ─── Etapa 3: Índices ────────────────────────────────────────────────────────


def criar_indices(target_col) -> None:
    target_col.create_index("nome_cientifico", unique=True)
    target_col.create_index("estados")
    target_col.create_index("biomas")
    target_col.create_index("contagem_ocorrencias")
    log.info("Índices criados/verificados em '%s'.", TARGET_COLLECTION)


# ─── Ponto de entrada ────────────────────────────────────────────────────────


def main():
    client = MongoClient(MONGO_URI)
    db = client[DATABASE]

    source_col = db[SOURCE_COLLECTION]
    target_col = db[TARGET_COLLECTION]

    log.info("=== Início do ETL ===")

    especies = extrair_e_transformar(source_col)
    carregar(target_col, especies)
    criar_indices(target_col)

    log.info("=== ETL concluído. Total de espécies carregadas: %d ===", len(especies))
    client.close()


if __name__ == "__main__":
    main()
