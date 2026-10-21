import logging
from pathlib import Path

NOME_LOGGER = "estoque"


def configurar_logging(arquivo_log: Path, console: bool = True) -> logging.Logger:
    """Configura o logger do Sistema de Estoque (arquivo + terminal)."""
    logger = logging.getLogger(NOME_LOGGER)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Evita handlers duplicados se for chamado mais de uma vez
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")

    Path(arquivo_log).parent.mkdir(parents=True, exist_ok=True)
    arquivo = logging.FileHandler(arquivo_log, encoding="utf-8")
    arquivo.setFormatter(formato)
    logger.addHandler(arquivo)

    if console:
        terminal = logging.StreamHandler()
        terminal.setFormatter(formato)
        logger.addHandler(terminal)

    return logger
