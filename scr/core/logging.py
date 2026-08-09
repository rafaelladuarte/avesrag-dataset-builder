import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado de forma centralizada."""
    full_name = f"BuilderAvesRAG.{name}" if name != "__main__" else "BuilderAvesRAG"
    logger = logging.getLogger(full_name)

    # Se o logger já tem handlers, evitamos duplicação
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Arquivo local de log
        file_handler = logging.FileHandler("avesrag.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Impede a propagação para o root logger
        logger.propagate = False

    return logger
