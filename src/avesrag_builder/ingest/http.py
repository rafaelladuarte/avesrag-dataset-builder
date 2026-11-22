"""GET de JSON com repetição, para as APIs públicas (Wikidata, Commons, iNaturalist).

Repete em 429, em 5xx e em falha de conexão (a medição de 22/11 perdeu a rota
para o iNaturalist no meio da coleta), esperando `Retry-After` quando a API
informa e, senão, um tempo crescente. Depois de cada resposta boa, espera
`intervalo` segundos, para respeitar o limite de requisições da API.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from avesrag_builder.core.logging import get_logger

log = get_logger(__name__)

TIMEOUT_S = 60
TENTATIVAS = 5
ESPERA_BASE_S = 15


class ClienteJson:
    def __init__(self, user_agent: str, intervalo: float = 0.0, dormir=time.sleep):
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = user_agent
        self.intervalo = intervalo
        self._dormir = dormir

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        for tentativa in range(1, TENTATIVAS + 1):
            espera = ESPERA_BASE_S * tentativa
            try:
                r = self.sessao.get(url, params=params, timeout=TIMEOUT_S)
            except (requests.ConnectionError, requests.Timeout) as e:
                if tentativa == TENTATIVAS:
                    raise
                log.warning("%s: %s; nova tentativa em %ss", url, type(e).__name__, espera)
                self._dormir(espera)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if tentativa == TENTATIVAS:
                    r.raise_for_status()
                retry_after = r.headers.get("Retry-After", "")
                espera = int(retry_after) if retry_after.isdigit() else espera
                log.warning("%s: HTTP %s; nova tentativa em %ss", url, r.status_code, espera)
                self._dormir(espera)
                continue
            r.raise_for_status()
            if self.intervalo:
                self._dormir(self.intervalo)
            return r.json()
        raise AssertionError("inalcançável")
