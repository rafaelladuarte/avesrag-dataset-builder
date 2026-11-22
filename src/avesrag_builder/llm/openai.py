"""Fornecedor OpenAI: Chat Completions com `json_schema` estrito, a API de batch e embeddings.

Usa HTTP direto (`requests`), sem o SDK: são só cinco endpoints.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from avesrag_builder.llm.base import (
    Embeddings,
    ErroFornecedor,
    Pedido,
    Resposta,
    SituacaoLote,
)

URL_BASE = "https://api.openai.com/v1"
ENDPOINT = "/v1/chat/completions"
TIMEOUT_S = 180

# Situação dos lotes na OpenAI -> situação no pipeline. Um lote `expired` entrega
# as respostas que ficaram prontas; as outras voltam a ser pendentes.
_SITUACAO = {
    "validating": "em_andamento",
    "in_progress": "em_andamento",
    "finalizing": "em_andamento",
    "cancelling": "em_andamento",
    "completed": "concluido",
    "expired": "concluido",
    "failed": "falhou",
    "cancelled": "falhou",
}


def corpo(pedido: Pedido) -> dict[str, Any]:
    """Corpo do Chat Completions; `temperature` só vai quando o prompt define."""
    body: dict[str, Any] = {
        "model": pedido.modelo,
        "messages": [
            {"role": "system", "content": pedido.system},
            {"role": "user", "content": pedido.entrada},
        ],
        "response_format": {"type": "json_schema", "json_schema": pedido.schema},
    }
    if pedido.temperatura is not None:
        body["temperature"] = pedido.temperatura
    return body


def resposta_de_corpo(custom_id: str, body: dict[str, Any]) -> Resposta:
    """Converte o corpo de um Chat Completion em `Resposta`."""
    uso = body.get("usage") or {}
    tokens = {
        "tokens_entrada": int(uso.get("prompt_tokens") or 0),
        "tokens_saida": int(uso.get("completion_tokens") or 0),
    }
    try:
        mensagem = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return Resposta(id=custom_id, erro="resposta sem choices", **tokens)
    if mensagem.get("refusal"):
        return Resposta(id=custom_id, erro=f"recusa: {mensagem['refusal']}", **tokens)
    return Resposta(id=custom_id, conteudo=mensagem.get("content"), **tokens)


def linha_de_resultado(linha: dict[str, Any]) -> Resposta:
    """Uma linha do arquivo de saída (ou de erros) de um lote."""
    custom_id = linha.get("custom_id") or ""
    if linha.get("error"):
        return Resposta(id=custom_id, erro=f"erro_api: {linha['error']}")
    response = linha.get("response") or {}
    if response.get("status_code") != 200:
        return Resposta(
            id=custom_id,
            erro=f"erro_api: HTTP {response.get('status_code')} {response.get('body')}",
        )
    return resposta_de_corpo(custom_id, response.get("body") or {})


class OpenAIFornecedor:
    nome = "openai"

    def __init__(self, api_key: str, url_base: str = URL_BASE, sessao: Any = None):
        self._url = url_base.rstrip("/")
        self._sessao = sessao or requests.Session()
        self._sessao.headers["Authorization"] = f"Bearer {api_key}"

    def _req(self, metodo: str, caminho: str, **kw: Any) -> requests.Response:
        try:
            r = self._sessao.request(metodo, self._url + caminho, timeout=TIMEOUT_S, **kw)
        except requests.RequestException as e:
            raise ErroFornecedor(f"{metodo} {caminho}: {e}") from e
        if r.status_code >= 400:
            raise ErroFornecedor(f"{metodo} {caminho}: HTTP {r.status_code} {r.text[:500]}")
        return r

    def gerar(self, pedido: Pedido) -> Resposta:
        try:
            r = self._req("POST", "/chat/completions", json=corpo(pedido))
        except ErroFornecedor as e:
            return Resposta(id=pedido.id, erro=f"erro_api: {e}")
        return resposta_de_corpo(pedido.id, r.json())

    def enviar_lote(self, pedidos: list[Pedido]) -> str:
        jsonl = "\n".join(
            json.dumps(
                {"custom_id": p.id, "method": "POST", "url": ENDPOINT, "body": corpo(p)},
                ensure_ascii=False,
            )
            for p in pedidos
        )
        arquivo = self._req(
            "POST",
            "/files",
            data={"purpose": "batch"},
            files={"file": ("extract.jsonl", jsonl.encode("utf-8"), "application/jsonl")},
        ).json()
        lote = self._req(
            "POST",
            "/batches",
            json={"input_file_id": arquivo["id"], "endpoint": ENDPOINT, "completion_window": "24h"},
        ).json()
        return lote["id"]

    def _lote(self, lote_id: str) -> dict[str, Any]:
        return self._req("GET", f"/batches/{lote_id}").json()

    def situacao_lote(self, lote_id: str) -> SituacaoLote:
        lote = self._lote(lote_id)
        status = lote.get("status", "")
        contagem = lote.get("request_counts") or {}
        detalhe = (
            f"{status}: {contagem.get('completed', 0)}/{contagem.get('total', 0)} prontos, "
            f"{contagem.get('failed', 0)} com erro"
        )
        if lote.get("errors"):
            detalhe += f"; {lote['errors']}"
        return SituacaoLote(status=_SITUACAO.get(status, "em_andamento"), detalhe=detalhe)

    def resultados_lote(self, lote_id: str) -> list[Resposta]:
        lote = self._lote(lote_id)
        respostas: list[Resposta] = []
        for chave in ("output_file_id", "error_file_id"):
            if not lote.get(chave):
                continue
            texto = self._req("GET", f"/files/{lote[chave]}/content").text
            for linha in texto.splitlines():
                if linha.strip():
                    respostas.append(linha_de_resultado(json.loads(linha)))
        return respostas

    def embeddings(self, textos: list[str], modelo: str) -> Embeddings:
        """`/embeddings` com vários textos numa chamada; a ordem vem do campo `index`."""
        if not textos:
            return Embeddings(vetores=[])
        body = self._req("POST", "/embeddings", json={"model": modelo, "input": textos}).json()
        dados = sorted(body.get("data") or [], key=lambda d: d["index"])
        if len(dados) != len(textos):
            raise ErroFornecedor(
                f"/embeddings devolveu {len(dados)} vetores para {len(textos)} textos"
            )
        tokens = int((body.get("usage") or {}).get("total_tokens") or 0)
        return Embeddings(vetores=[d["embedding"] for d in dados], tokens=tokens)
