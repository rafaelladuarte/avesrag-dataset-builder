"""Cliente de LLM do builder: interface de fornecedor (`base`) e implementações."""

from avesrag_builder.core.settings import Settings
from avesrag_builder.llm.base import Embedder, Fornecedor


def fornecedor(settings: Settings) -> Fornecedor:
    """Implementação escolhida por `LLM_PROVIDER`; cobra a chave de API."""
    if settings.LLM_PROVIDER == "openai":
        from avesrag_builder.llm.openai import OpenAIFornecedor

        settings.require("OPENAI_API_KEY")
        return OpenAIFornecedor(settings.OPENAI_API_KEY.get_secret_value())
    raise ValueError(f"LLM_PROVIDER desconhecido: {settings.LLM_PROVIDER!r}")


def embedder(settings: Settings) -> Embedder:
    """Embeddings pelo mesmo fornecedor do LLM (`EMBEDDING_MODEL`); cobra a chave de API."""
    if settings.LLM_PROVIDER == "openai":
        from avesrag_builder.llm.openai import OpenAIFornecedor

        settings.require("OPENAI_API_KEY")
        return OpenAIFornecedor(settings.OPENAI_API_KEY.get_secret_value())
    raise ValueError(f"LLM_PROVIDER desconhecido: {settings.LLM_PROVIDER!r}")
