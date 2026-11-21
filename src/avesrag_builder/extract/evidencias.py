"""Conferência de evidências: cada trecho citado pelo LLM existe no texto de entrada?

A comparação ignora caixa, acentos, pontuação e espaços repetidos, para que
"cinza-claro," e "cinza claro" casem. Reticências e trechos emendados não casam.
"""

from __future__ import annotations

import re
from typing import Any

from avesrag_builder.core.texto import normalize


def normalizar_para_busca(texto: str) -> str:
    texto = normalize(texto)
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def evidencias(saida: dict[str, Any]) -> list[str]:
    """Todas as evidências da saída de um prompt, na ordem dos campos."""
    encontradas: list[str] = []
    for valor in saida.values():
        itens = valor if isinstance(valor, list) else [valor]
        for item in itens:
            if isinstance(item, dict) and "evidencia" in item:
                encontradas.append(item["evidencia"])
    return encontradas


def nao_encontradas(saida: dict[str, Any], texto_fonte: str) -> list[str]:
    """Evidências que não aparecem no texto de entrada (sem repetir)."""
    alvo = f" {normalizar_para_busca(texto_fonte)} "
    faltando: list[str] = []
    for ev in evidencias(saida):
        trecho = normalizar_para_busca(ev)
        if (not trecho or f" {trecho} " not in alvo) and ev not in faltando:
            faltando.append(ev)
    return faltando
