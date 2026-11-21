"""Normalização de texto compartilhada entre as etapas."""

import re
import unicodedata


def normalize(text: str) -> str:
    """Lowercase, remove acentos e apóstrofos para comparação."""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("'", "").replace("`", "")
    return text


def normalizar_termo(text: str) -> str:
    """Forma de comparação de termos do vocabulário.

    Igual a `normalize`, tratando hífen e underscore como espaço:
    "Cinza-Escuro" -> "cinza escuro", "borda_de_mata" -> "borda de mata".
    """
    text = normalize(text)
    text = re.sub(r"[-_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()
