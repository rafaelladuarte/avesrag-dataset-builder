"""Interface de fornecedor de LLM usada pelo `extract`.

O pipeline só conhece `Pedido`, `Resposta` e o protocolo `Fornecedor`; a OpenAI
é uma implementação (`llm/openai.py`). Os testes usam um fornecedor falso.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

StatusLote = Literal["em_andamento", "concluido", "falhou"]


@dataclass(frozen=True)
class Pedido:
    """Uma chamada ao LLM com saída em JSON Schema estrito."""

    id: str  # custom_id: "<species_id>:<prompt>:<input_hash[:12]>"
    modelo: str
    system: str
    entrada: str
    schema: dict[str, Any]  # {"name", "strict", "schema"} (formato json_schema da OpenAI)
    temperatura: float | None = None


@dataclass(frozen=True)
class Resposta:
    """Resultado de um pedido: o JSON devolvido (texto) ou o erro da API."""

    id: str
    conteudo: str | None = None
    erro: str | None = None
    tokens_entrada: int = 0
    tokens_saida: int = 0


@dataclass(frozen=True)
class SituacaoLote:
    status: StatusLote
    detalhe: str = ""


class ErroFornecedor(RuntimeError):
    """Falha de comunicação com o fornecedor (rede, autenticação, lote rejeitado)."""


class Fornecedor(Protocol):
    nome: str

    def gerar(self, pedido: Pedido) -> Resposta:
        """Chamada síncrona. Erro da API volta em `Resposta.erro`, sem exceção."""
        ...

    def enviar_lote(self, pedidos: list[Pedido]) -> str:
        """Envia os pedidos à API de batch e devolve o id do lote."""
        ...

    def situacao_lote(self, lote_id: str) -> SituacaoLote: ...

    def resultados_lote(self, lote_id: str) -> list[Resposta]:
        """Respostas de um lote concluído (pedidos sem resposta ficam de fora)."""
        ...


@dataclass(frozen=True)
class Embeddings:
    """Vetores na mesma ordem dos textos enviados, e os tokens cobrados."""

    vetores: list[list[float]]
    tokens: int = 0


class Embedder(Protocol):
    nome: str

    def embeddings(self, textos: list[str], modelo: str) -> Embeddings:
        """Um vetor por texto, na mesma ordem. Falha com `ErroFornecedor`."""
        ...
