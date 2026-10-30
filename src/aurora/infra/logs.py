"""Configuração de logs no formato `chave=valor`."""

import logging
import sys

__all__ = ["configurar_logs"]


def configurar_logs(nivel: str = "INFO") -> None:
    """Configura o `logging` padrão para o stdout. Não logar texto de mensagens nem nomes de visitantes."""
    logging.basicConfig(
        level=nivel,
        stream=sys.stdout,
        format="ts=%(asctime)s nivel=%(levelname)s logger=%(name)s %(message)s",
        force=True,
    )
