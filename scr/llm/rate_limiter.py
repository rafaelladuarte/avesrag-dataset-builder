import random
import re
import threading
import time
from datetime import datetime, timezone

from scr.core.config import settings
from scr.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Controle de rate limiting client-side para a Gemini API.

    Gerencia 3 dimensões:
    - RPM: Requests per minute (intervalo mínimo entre chamadas)
    - TPM: Tokens per minute (rastreado via usage_metadata)
    - RPD: Requests per day (contador diário)
    """

    def __init__(
        self,
        rpm: int = 0,
        tpm: int = 0,
        rpd: int = 0,
    ):
        # Limites (0 = sem limite, usa config)
        self.rpm = rpm or settings.GEMINI_RPM
        self.tpm = tpm or settings.GEMINI_TPM
        self.rpd = rpd or settings.GEMINI_RPD

        # Estado interno
        self._lock = threading.Lock()
        self._request_times: list[float] = []  # timestamps das últimas requests
        self._token_usage: list[tuple[float, int]] = []  # (timestamp, tokens)
        self._daily_count = 0
        self._daily_reset_date = datetime.now(timezone.utc).date()

        # Intervalo mínimo entre requests (baseado no RPM)
        self._min_interval = 60.0 / self.rpm if self.rpm > 0 else 0.0

        logger.info(f"RateLimiter inicializado: RPM={self.rpm}, TPM={self.tpm}, RPD={self.rpd}")

    def wait_if_needed(self) -> None:
        """Bloqueia até que seja seguro fazer a próxima requisição."""
        with self._lock:
            now = time.monotonic()

            # Reset diário
            today = datetime.now(timezone.utc).date()
            if today != self._daily_reset_date:
                self._daily_count = 0
                self._daily_reset_date = today
                logger.info("Contador diário resetado.")

            # Check RPD
            if self.rpd > 0 and self._daily_count >= self.rpd:
                logger.warning(
                    f"Limite diário atingido ({self.rpd} RPD). "
                    f"Aguardando reset à meia-noite UTC."
                )
                raise RateLimitExceededError(f"Limite diário de {self.rpd} requisições atingido.")

            # Check RPM — intervalo mínimo entre requests
            if self._min_interval > 0 and self._request_times:
                elapsed = now - self._request_times[-1]
                if elapsed < self._min_interval:
                    sleep_time = self._min_interval - elapsed
                    logger.debug(f"Rate limit RPM: aguardando {sleep_time:.1f}s")
                    time.sleep(sleep_time)

            # Check TPM — limpar entradas mais velhas que 60s
            if self.tpm > 0:
                cutoff = now - 60.0
                self._token_usage = [(t, tokens) for t, tokens in self._token_usage if t > cutoff]
                tokens_last_minute = sum(tokens for _, tokens in self._token_usage)

                if tokens_last_minute >= self.tpm:
                    # Esperar até que a janela de 1 min libere espaço
                    oldest_time = self._token_usage[0][0]
                    sleep_time = 60.0 - (now - oldest_time) + 1.0
                    logger.warning(
                        f"Limite TPM atingido ({tokens_last_minute}/{self.tpm}). "
                        f"Aguardando {sleep_time:.1f}s."
                    )
                    time.sleep(sleep_time)

    def record_usage(self, total_tokens: int) -> None:
        """Registra o uso de uma requisição bem-sucedida."""
        with self._lock:
            now = time.monotonic()
            self._request_times.append(now)
            self._daily_count += 1

            if self.tpm > 0:
                self._token_usage.append((now, total_tokens))

            # Limpar timestamps antigos (> 60s)
            cutoff = now - 60.0
            self._request_times = [t for t in self._request_times if t > cutoff]

            logger.debug(
                f"Uso registrado: {total_tokens} tokens | "
                f"RPM={len(self._request_times)}/{self.rpm} | "
                f"RPD={self._daily_count}/{self.rpd}"
            )

    @staticmethod
    def parse_retry_delay(error: Exception) -> float:
        """Extrai o retryDelay da mensagem de erro 429."""
        error_str = str(error)
        match = re.search(r"retry in (\d+\.?\d*)s", error_str, re.IGNORECASE)
        if match:
            return float(match.group(1))

        # Tenta o campo retryDelay do JSON
        match = re.search(r"'retryDelay':\s*'(\d+)s'", error_str)
        if match:
            return float(match.group(1))

        # Fallback
        return 15.0

    def handle_rate_limit_error(self, error: Exception) -> None:
        """Trata erro 429 esperando o tempo indicado pelo servidor."""
        delay = self.parse_retry_delay(error)
        # Adiciona jitter de 1-3s para evitar thundering herd
        jitter = random.uniform(1.0, 3.0)
        total_wait = delay + jitter

        logger.warning(
            f"Rate limit 429 recebido. "
            f"retryDelay={delay:.1f}s + jitter={jitter:.1f}s = {total_wait:.1f}s"
        )
        time.sleep(total_wait)


class RateLimitExceededError(Exception):
    """Exceção quando o limite diário é atingido."""

    pass
