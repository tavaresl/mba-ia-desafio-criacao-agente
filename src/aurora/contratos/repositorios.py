"""Contratos de persistência (implementados em `aurora.persistencia`)."""

from collections.abc import Callable
from datetime import date
from typing import Protocol

from aurora.contratos.modelos import (
    Area,
    DadosIniciais,
    Indisponivel,
    NaoEncontrada,
    Reserva,
    ReservaCancelada,
    ReservaCriada,
    Visitante,
)

__all__ = [
    "CatalogoReferencia",
    "IndiceSessoes",
    "RepositorioCargaInicial",
    "RepositorioReservas",
    "RepositorioVisitantes",
]


class RepositorioReservas(Protocol):
    async def criar(
        self, *, apartamento: str, area_id: str, data: date, gerar_codigo: Callable[[], str]
    ) -> ReservaCriada | Indisponivel: ...

    async def cancelar_ativa(
        self, *, apartamento: str, area_id: str, data: date
    ) -> ReservaCancelada | NaoEncontrada: ...

    async def cancelar_por_codigo(self, *, apartamento: str, codigo: str) -> ReservaCancelada | NaoEncontrada: ...

    async def listar_ativas(self, apartamento: str) -> list[Reserva]: ...

    async def esta_ocupada(self, *, area_id: str, data: date) -> bool: ...


class RepositorioVisitantes(Protocol):
    async def autorizar(self, *, apartamento: str, nome: str, data: date) -> Visitante: ...

    async def listar(self, apartamento: str) -> list[Visitante]: ...


class CatalogoReferencia(Protocol):
    async def listar_areas(self) -> list[Area]: ...

    async def apartamento_existe(self, numero: str) -> bool: ...


class IndiceSessoes(Protocol):
    async def registrar(self, *, session_id: str, apartamento: str) -> None: ...

    async def apartamento_de(self, session_id: str) -> str | None: ...

    async def remover(self, session_id: str) -> None: ...

    async def limpar(self) -> None: ...


class RepositorioCargaInicial(Protocol):
    async def criar_esquema(self) -> None: ...

    async def seed_aplicado(self) -> bool: ...

    async def restaurar(self, dados: DadosIniciais) -> None: ...
