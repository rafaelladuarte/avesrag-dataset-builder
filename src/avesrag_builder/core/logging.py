import logging
import os
import sys

PREFIXO = "BuilderAvesRAG"
_nivel = logging.INFO


def set_level(level: str | int) -> None:
    """Muda o nível de todos os loggers do builder, inclusive os já criados."""
    global _nivel
    nivel = logging.getLevelName(level.upper()) if isinstance(level, str) else level
    if not isinstance(nivel, int):
        raise ValueError(f"nível de log inválido: {level!r}")
    _nivel = nivel
    for nome, logger in logging.root.manager.loggerDict.items():
        if nome == PREFIXO or nome.startswith(PREFIXO + "."):
            if isinstance(logger, logging.Logger):
                logger.setLevel(_nivel)


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado de forma centralizada."""
    full_name = f"{PREFIXO}.{name}" if name != "__main__" else PREFIXO
    logger = logging.getLogger(full_name)

    # Se o logger já tem handlers, evitamos duplicação
    if not logger.handlers:
        logger.setLevel(_nivel)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Arquivo de log opcional (AVESRAG_LOG_FILE); sem ele, só console
        log_file = os.environ.get("AVESRAG_LOG_FILE")
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Impede a propagação para o root logger
        logger.propagate = False

    return logger
