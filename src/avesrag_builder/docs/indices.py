"""Índices `$vectorSearch` e `$search` em `species_retrieval_docs` (etapa 7, `index`).

- `vetor_especies`: o embedding (3.072 posições, cosseno), com `dominio`,
  `species_id` e cada chave de `filtros` declarados como filtro.
- `texto_especies`: `texto` e `nomes` com o analisador `lucene.portuguese`.

Idempotente: cria o que não existe, atualiza o que tem outra definição e não
mexe no que já está igual. Depois, espera os índices ficarem consultáveis e o
`mongot` terminar de indexar os documentos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pymongo.database import Database
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

from avesrag_builder.core.logging import get_logger
from avesrag_builder.core.models import EMBEDDING_DIM
from avesrag_builder.db.busca import BuscaIndisponivel, _esperar
from avesrag_builder.db.collections import SPECIES_RETRIEVAL_DOCS
from avesrag_builder.docs.montar import CHAVES_FILTRO

log = get_logger(__name__)

INDICE_VETOR = "vetor_especies"
INDICE_TEXTO = "texto_especies"
ANALISADOR = "lucene.portuguese"

Acao = Literal["criado", "atualizado", "inalterado"]


def definicao_vetor(dimensoes: int = EMBEDDING_DIM) -> dict[str, Any]:
    return {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": dimensoes,
                "similarity": "cosine",
            },
            {"type": "filter", "path": "dominio"},
            {"type": "filter", "path": "species_id"},
            *({"type": "filter", "path": f"filtros.{chave}"} for chave in CHAVES_FILTRO),
        ]
    }


def definicao_texto() -> dict[str, Any]:
    campo = {"type": "string", "analyzer": ANALISADOR}
    return {"mappings": {"dynamic": False, "fields": {"texto": campo, "nomes": campo}}}


def definicoes(dimensoes: int = EMBEDDING_DIM) -> dict[str, tuple[str, dict[str, Any]]]:
    """nome -> (tipo, definição)."""
    return {
        INDICE_VETOR: ("vectorSearch", definicao_vetor(dimensoes)),
        INDICE_TEXTO: ("search", definicao_texto()),
    }


def contem(atual: Any, esperado: Any) -> bool:
    """`esperado` está contido em `atual`? O servidor acrescenta valores padrão à
    definição gravada; a lista de campos do índice vetorial vale sem ordem."""
    if isinstance(esperado, dict):
        return isinstance(atual, dict) and all(
            k in atual and contem(atual[k], v) for k, v in esperado.items()
        )
    if isinstance(esperado, list):
        if not isinstance(atual, list) or len(atual) != len(esperado):
            return False
        restantes = list(atual)
        for item in esperado:
            achado = next((a for a in restantes if contem(a, item)), None)
            if achado is None:
                return False
            restantes.remove(achado)
        return True
    return atual == esperado


@dataclass
class ResultadoIndices:
    acoes: dict[str, Acao] = field(default_factory=dict)
    documentos: int = 0

    def linhas(self) -> list[str]:
        acoes = ", ".join(f"{nome} {acao}" for nome, acao in self.acoes.items())
        return [f"index: {acoes}; {self.documentos} documentos indexados"]


def garantir(
    db: Database, dimensoes: int = EMBEDDING_DIM, timeout_s: float = 300
) -> ResultadoIndices:
    col = db[SPECIES_RETRIEVAL_DOCS]
    if SPECIES_RETRIEVAL_DOCS not in db.list_collection_names():
        db.create_collection(SPECIES_RETRIEVAL_DOCS)
    res = ResultadoIndices()
    atuais = {i["name"]: i for i in col.list_search_indexes()}
    try:
        for nome, (tipo, definicao) in definicoes(dimensoes).items():
            atual = atuais.get(nome)
            if atual is None:
                col.create_search_index(SearchIndexModel(definicao, name=nome, type=tipo))
                res.acoes[nome] = "criado"
            elif contem(atual.get("latestDefinition") or {}, definicao):
                res.acoes[nome] = "inalterado"
            else:
                col.update_search_index(nome, definicao)
                res.acoes[nome] = "atualizado"
    except OperationFailure as e:
        raise BuscaIndisponivel(f"o servidor recusou o índice de busca: {e}") from e

    nomes = set(definicoes(dimensoes))

    def _prontos() -> bool:
        indices = [i for i in col.list_search_indexes() if i["name"] in nomes]
        return len(indices) == len(nomes) and all(
            i.get("queryable") and i.get("status") == "READY" for i in indices
        )

    _esperar(_prontos, timeout_s, "os índices de busca ficarem prontos")
    res.documentos = esperar_indexacao(db, timeout_s)
    for nome, acao in res.acoes.items():
        log.info(f"índice {nome}: {acao}")
    return res


def esperar_indexacao(db: Database, timeout_s: float = 300) -> int:
    """Espera o `$vectorSearch` enxergar todos os documentos (o mongot indexa depois)."""
    col = db[SPECIES_RETRIEVAL_DOCS]
    total = col.count_documents({})
    if total == 0:
        return 0
    vetor = col.find_one({}, {"embedding": 1})["embedding"]
    alvo = min(10_000, total)  # o $vectorSearch aceita até 10 mil candidatos

    def _todos() -> bool:
        achados = col.aggregate(
            [
                {
                    "$vectorSearch": {
                        "index": INDICE_VETOR,
                        "path": "embedding",
                        "queryVector": vetor,
                        "numCandidates": alvo,
                        "limit": alvo,
                    }
                },
                {"$count": "n"},
            ]
        )
        return next(achados, {"n": 0})["n"] >= alvo

    _esperar(_todos, timeout_s, f"o mongot indexar os {total} documentos")
    return total
