"""Tools de reservas: adaptadores finos sobre `ServicoReservas` (ADR-001).

Nenhuma tool declara parâmetro de apartamento: ele vem de `tool_context.user_id`.
"""

from typing import Any

from google.adk.tools import BaseTool, FunctionTool, ToolContext

from aurora.agentes.identidade import apartamento_da_sessao
from aurora.agentes.serializacao import serializar, serializar_areas, serializar_reservas
from aurora.contratos import ServicoReservas

__all__ = ["criar_ferramentas_reservas"]


def criar_ferramentas_reservas(servico: ServicoReservas) -> list[BaseTool]:
    async def listar_areas(tool_context: ToolContext) -> dict[str, Any]:
        """Lista as áreas comuns reserváveis, com o id a usar nas demais ferramentas e a taxa em reais."""
        return serializar_areas(servico.listar_areas())

    async def consultar_disponibilidade(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
        """Informa se uma área está livre numa data. Responde apenas livre ou ocupada, nunca de quem é.

        Args:
            area: Id da área (ex.: salao-de-festas, churrasqueira, quadra).
            data: Data no formato AAAA-MM-DD.
        """
        return serializar(await servico.consultar_disponibilidade(area=area, data=data))

    async def listar_minhas_reservas(tool_context: ToolContext) -> dict[str, Any]:
        """Lista as reservas ativas do apartamento do morador atual."""
        return serializar_reservas(await servico.listar_do_apartamento(apartamento_da_sessao(tool_context)))

    async def reservar_area(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
        """Reserva uma área comum para o apartamento do morador atual numa data.

        Áreas com taxa ficam pendentes até o morador confirmar pelo canal de confirmações do aplicativo.

        Args:
            area: Id da área (ex.: salao-de-festas, churrasqueira, quadra).
            data: Data no formato AAAA-MM-DD.
        """
        resultado = await servico.reservar(apartamento=apartamento_da_sessao(tool_context), area=area, data=data)
        return serializar(resultado)

    async def cancelar_reserva(
        tool_context: ToolContext, area: str | None = None, data: str | None = None, codigo: str | None = None
    ) -> dict[str, Any]:
        """Cancela uma reserva do apartamento do morador atual, sem confirmação.

        Informe o código da reserva, ou a área e a data.

        Args:
            area: Id da área da reserva.
            data: Data da reserva no formato AAAA-MM-DD.
            codigo: Código da reserva.
        """
        resultado = await servico.cancelar(
            apartamento=apartamento_da_sessao(tool_context), area=area, data=data, codigo=codigo
        )
        return serializar(resultado)

    def reserva_gera_cobranca(area: str, **_demais_argumentos: Any) -> bool:
        """Predicado de `require_confirmation`: a decisão vem do domínio, nunca do modelo (fail-closed)."""
        return servico.exige_confirmacao(area)

    return [
        FunctionTool(listar_areas),
        FunctionTool(consultar_disponibilidade),
        FunctionTool(listar_minhas_reservas),
        FunctionTool(reservar_area, require_confirmation=reserva_gera_cobranca),
        FunctionTool(cancelar_reserva),
    ]
