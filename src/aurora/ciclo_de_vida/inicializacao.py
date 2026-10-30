"""Preparação do banco na subida da API (ADR-016)."""

import logging
from collections.abc import Callable

from aurora.contratos import DadosIniciais, RepositorioCargaInicial

__all__ = ["preparar_banco"]

_LOG = logging.getLogger(__name__)


async def preparar_banco(carga: RepositorioCargaInicial, dados_iniciais: Callable[[], DadosIniciais]) -> bool:
    """Cria o esquema (idempotente) e aplica o seed só se o marcador `seed_aplicado` não existir.

    Nunca restaura um banco já semeado, nem que esteja vazio: a restauração é um comando à parte.
    Os JSON só são lidos quando o seed é necessário.

    Returns:
        True se o seed foi aplicado nesta chamada.
    """
    await carga.criar_esquema()
    if await carga.seed_aplicado():
        return False
    dados = dados_iniciais()
    await carga.restaurar(dados)
    _LOG.info("seed_inicial_aplicado reservas=%d visitantes=%d", len(dados.reservas), len(dados.visitantes))
    return True
