"""Contratos dos serviços de domínio (implementados em `aurora.dominio`)."""

from typing import Protocol

from aurora.contratos.modelos import (
    Area,
    Reserva,
    ResultadoCancelamento,
    ResultadoConsulta,
    ResultadoReserva,
    ResultadoVisitante,
    Visitante,
)

__all__ = ["ServicoReservas", "ServicoVisitantes"]


class ServicoReservas(Protocol):
    def listar_areas(self) -> list[Area]: ...

    def resolver_area(self, area: str) -> Area | None: ...

    def exige_confirmacao(self, area: str) -> bool: ...

    async def consultar_disponibilidade(self, *, area: str, data: str) -> ResultadoConsulta: ...

    async def reservar(self, *, apartamento: str, area: str, data: str) -> ResultadoReserva: ...

    async def cancelar(
        self, *, apartamento: str, area: str | None = None, data: str | None = None, codigo: str | None = None
    ) -> ResultadoCancelamento: ...

    async def listar_do_apartamento(self, apartamento: str) -> list[Reserva]: ...


class ServicoVisitantes(Protocol):
    async def autorizar(self, *, apartamento: str, nome: str, data: str) -> ResultadoVisitante: ...

    async def listar_do_apartamento(self, apartamento: str) -> list[Visitante]: ...
