"""Objeto com os serviços que as rotas consomem (apenas contratos)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aurora.contratos import ServicoConversa, ServicoReservas, ServicoVisitantes

__all__ = ["Aplicacao"]


@dataclass(slots=True)
class Aplicacao:
    conversa: ServicoConversa
    reservas: ServicoReservas
    visitantes: ServicoVisitantes
    fechar: Callable[[], Awaitable[None]]
