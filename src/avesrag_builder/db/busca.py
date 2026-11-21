"""Verificação de que o MongoDB local aceita índices $vectorSearch e $search.

Cria uma collection temporária, os dois índices e uma consulta de cada tipo,
e apaga tudo no fim. Usada por `avesrag-builder index --verificar` e pelo
teste de integração.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from pymongo.database import Database
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

from avesrag_builder.core.logging import get_logger

logger = get_logger(__name__)

PREFIXO_COLLECTION = "_avesrag_verificacao_"
VERSAO_MINIMA = (8, 2)

_DOCS = [
    {
        "_id": "a",
        "v": [1.0, 0.0, 0.0, 0.0],
        "cor": "amarelo",
        "texto": "barriga amarela e mascara preta",
    },
    {"_id": "b", "v": [0.9, 0.1, 0.0, 0.0], "cor": "preto", "texto": "ave toda preta"},
    {"_id": "c", "v": [0.0, 1.0, 0.0, 0.0], "cor": "amarelo", "texto": "bico enorme e colorido"},
]


class BuscaIndisponivel(RuntimeError):
    """O servidor não aceitou os índices ou as consultas de busca."""


@dataclass
class ResultadoVerificacao:
    versao_servidor: str
    vector_search: list[str]
    text_search: list[str]


def versao_servidor(db: Database) -> str:
    return db.client.server_info()["version"]


def _versao_tupla(versao: str) -> tuple[int, ...]:
    return tuple(int(p) for p in versao.split("-")[0].split(".")[:2])


def _esperar(condicao, timeout_s: float, descricao: str, intervalo_s: float = 1.0):
    limite = time.monotonic() + timeout_s
    while True:
        resultado = condicao()
        if resultado:
            return resultado
        if time.monotonic() > limite:
            raise BuscaIndisponivel(f"tempo esgotado ({timeout_s:.0f}s) esperando {descricao}")
        time.sleep(intervalo_s)


def verificar_busca(db: Database, timeout_s: float = 120) -> ResultadoVerificacao:
    """Cria e consulta um índice vetorial e um textual numa collection temporária."""
    versao = versao_servidor(db)
    if _versao_tupla(versao) < VERSAO_MINIMA:
        raise BuscaIndisponivel(
            f"MongoDB {versao}; a busca vetorial exige {'.'.join(map(str, VERSAO_MINIMA))}+ "
            "com mongot (use a imagem mongodb-atlas-local do docker-compose)"
        )

    nome = f"{PREFIXO_COLLECTION}{uuid.uuid4().hex[:8]}"
    col = db[nome]
    try:
        col.insert_many(_DOCS)
        try:
            col.create_search_indexes(
                [
                    SearchIndexModel(
                        name="vetor",
                        type="vectorSearch",
                        definition={
                            "fields": [
                                {
                                    "type": "vector",
                                    "path": "v",
                                    "numDimensions": 4,
                                    "similarity": "cosine",
                                },
                                {"type": "filter", "path": "cor"},
                            ]
                        },
                    ),
                    SearchIndexModel(
                        name="texto",
                        type="search",
                        definition={
                            "mappings": {"dynamic": False, "fields": {"texto": {"type": "string"}}}
                        },
                    ),
                ]
            )
        except OperationFailure as e:
            raise BuscaIndisponivel(f"o servidor recusou criar índices de busca: {e}") from e

        def _prontos():
            indices = list(col.list_search_indexes())
            return len(indices) == 2 and all(i.get("queryable") for i in indices)

        _esperar(_prontos, timeout_s, "os índices ficarem consultáveis")

        # O mongot indexa os documentos de forma assíncrona: repete até aparecerem.
        def _vetorial():
            return [
                d["_id"]
                for d in col.aggregate(
                    [
                        {
                            "$vectorSearch": {
                                "index": "vetor",
                                "path": "v",
                                "queryVector": [1.0, 0.0, 0.0, 0.0],
                                "numCandidates": 10,
                                "limit": 3,
                                "filter": {"cor": "amarelo"},
                            }
                        },
                        {"$project": {"_id": 1}},
                    ]
                )
            ]

        def _textual():
            return [
                d["_id"]
                for d in col.aggregate(
                    [
                        {
                            "$search": {
                                "index": "texto",
                                "text": {"query": "bico colorido", "path": "texto"},
                            }
                        },
                        {"$project": {"_id": 1}},
                    ]
                )
            ]

        vetorial = _esperar(_vetorial, timeout_s, "resultados do $vectorSearch")
        textual = _esperar(_textual, timeout_s, "resultados do $search")
    finally:
        col.drop()

    if vetorial != ["a", "c"]:
        raise BuscaIndisponivel(
            f"$vectorSearch com filtro devolveu {vetorial}; esperado ['a', 'c']"
        )
    if textual[:1] != ["c"]:
        raise BuscaIndisponivel(f"$search devolveu {textual}; esperado 'c' primeiro")
    return ResultadoVerificacao(versao_servidor=versao, vector_search=vetorial, text_search=textual)
