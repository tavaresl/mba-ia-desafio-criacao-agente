"""Regras de reserva e cancelamento (RN-01, RN-02, RN-04, RN-05)."""

from collections.abc import Callable

from aurora.contratos import (
    Area,
    Disponibilidade,
    EntradaInvalida,
    MotivoInvalido,
    RepositorioReservas,
    Reserva,
    ResultadoCancelamento,
    ResultadoConsulta,
    ResultadoReserva,
)
from aurora.dominio.areas import CatalogoAreas
from aurora.dominio.codigos import gerar_codigo_reserva
from aurora.dominio.validacao import interpretar_data

__all__ = ["ServicoReservasPadrao"]


class ServicoReservasPadrao:
    """Implementa `aurora.contratos.ServicoReservas`. Sem estado mutável e sem check-then-insert."""

    def __init__(
        self,
        *,
        reservas: RepositorioReservas,
        areas: CatalogoAreas,
        gerar_codigo: Callable[[], str] = gerar_codigo_reserva,
    ) -> None:
        self._reservas = reservas
        self._areas = areas
        self._gerar_codigo = gerar_codigo

    def listar_areas(self) -> list[Area]:
        return self._areas.listar()

    def resolver_area(self, area: str) -> Area | None:
        return self._areas.resolver(area)

    def exige_confirmacao(self, area: str) -> bool:
        return self._areas.exige_confirmacao(area)

    async def consultar_disponibilidade(self, *, area: str, data: str) -> ResultadoConsulta:
        """Responde apenas livre/ocupada, nunca o dono da reserva (G2)."""
        entrada = self._validar(area, data)
        if isinstance(entrada, EntradaInvalida):
            return entrada
        encontrada, dia = entrada
        ocupada = await self._reservas.esta_ocupada(area_id=encontrada.id, data=dia)
        return Disponibilidade(encontrada.id, dia, not ocupada)

    async def reservar(self, *, apartamento: str, area: str, data: str) -> ResultadoReserva:
        """A exclusividade é decidida na gravação (ADR-013); aqui só se repassa o resultado."""
        entrada = self._validar(area, data)
        if isinstance(entrada, EntradaInvalida):
            return entrada
        encontrada, dia = entrada
        return await self._reservas.criar(
            apartamento=apartamento, area_id=encontrada.id, data=dia, gerar_codigo=self._gerar_codigo
        )

    async def cancelar(
        self, *, apartamento: str, area: str | None = None, data: str | None = None, codigo: str | None = None
    ) -> ResultadoCancelamento:
        """Cancela só reservas do próprio apartamento; reserva de terceiro vira `NaoEncontrada`."""
        if codigo and codigo.strip():
            return await self._reservas.cancelar_por_codigo(apartamento=apartamento, codigo=codigo.strip().upper())
        if not area or not data:
            return EntradaInvalida(MotivoInvalido.IDENTIFICACAO_INCOMPLETA)
        entrada = self._validar(area, data)
        if isinstance(entrada, EntradaInvalida):
            return entrada
        encontrada, dia = entrada
        return await self._reservas.cancelar_ativa(apartamento=apartamento, area_id=encontrada.id, data=dia)

    async def listar_do_apartamento(self, apartamento: str) -> list[Reserva]:
        return await self._reservas.listar_ativas(apartamento)

    def _validar(self, area: str, data: str):  # noqa: ANN202
        encontrada = self._areas.resolver(area)
        if encontrada is None:
            return EntradaInvalida(MotivoInvalido.AREA_INEXISTENTE)
        dia = interpretar_data(data)
        if dia is None:
            return EntradaInvalida(MotivoInvalido.DATA_INVALIDA)
        return encontrada, dia
