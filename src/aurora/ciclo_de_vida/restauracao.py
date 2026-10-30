"""Restauração dos dados iniciais (comando `aurora-restaurar`)."""

import logging
from dataclasses import dataclass
from pathlib import Path

from aurora.contratos import DadosIniciais, IndiceSessoes, RepositorioCargaInicial

__all__ = ["ResumoRestauracao", "restaurar"]

_LOG = logging.getLogger(__name__)
_SUFIXOS_SQLITE = ("", "-wal", "-shm")


@dataclass(frozen=True, slots=True)
class ResumoRestauracao:
    reservas: int
    visitantes: int
    sessoes_apagadas: bool


async def restaurar(
    *, carga: RepositorioCargaInicial, indice_sessoes: IndiceSessoes, banco_sessoes: Path, dados: DadosIniciais
) -> ResumoRestauracao:
    """Restaura o domínio (transação única), limpa o índice e apaga o banco de sessões do ADK.

    Idempotente: se algo falhar depois da restauração do domínio, repetir o comando completa o resto.
    A API não pode estar em execução.
    """
    await carga.criar_esquema()
    await carga.restaurar(dados)
    await indice_sessoes.limpar()
    for sufixo in _SUFIXOS_SQLITE:
        Path(f"{banco_sessoes}{sufixo}").unlink(missing_ok=True)
    _LOG.info(
        "restauracao_concluida reservas=%d visitantes=%d sessoes_apagadas=true",
        len(dados.reservas),
        len(dados.visitantes),
    )
    return ResumoRestauracao(len(dados.reservas), len(dados.visitantes), sessoes_apagadas=True)
