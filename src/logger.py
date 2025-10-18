import logging
import os
from logging import StreamHandler, Formatter

_LEVEL_MAP = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

def setup_logger(name: str = "api_extractor") -> logging.Logger:
    level = _LEVEL_MAP.get(os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evita handlers duplicados ao chamar múltiplas vezes
    if logger.handlers:
        return logger

    ch = StreamHandler()
    ch.setLevel(level)
    fmt = Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    logger.propagate = False
    return logger