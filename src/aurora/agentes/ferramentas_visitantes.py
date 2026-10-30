"""Tools de visitantes: adaptadores finos sobre `ServicoVisitantes`."""

from typing import Any

from google.adk.tools import BaseTool, FunctionTool, ToolContext

from aurora.agentes.identidade import apartamento_da_sessao
from aurora.agentes.serializacao import serializar, serializar_visitantes
from aurora.contratos import ServicoVisitantes

__all__ = ["criar_ferramentas_visitantes"]


def criar_ferramentas_visitantes(servico: ServicoVisitantes) -> list[BaseTool]:
    async def listar_meus_visitantes(tool_context: ToolContext) -> dict[str, Any]:
        """Lista os visitantes autorizados pelo apartamento do morador atual."""
        return serializar_visitantes(await servico.listar_do_apartamento(apartamento_da_sessao(tool_context)))

    async def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
        """Autoriza a entrada de um visitante no prédio numa data. Sempre fica pendente de confirmação do morador.

        Args:
            nome: Nome completo do visitante.
            data: Data da visita no formato AAAA-MM-DD.
        """
        resultado = await servico.autorizar(apartamento=apartamento_da_sessao(tool_context), nome=nome, data=data)
        return serializar(resultado)

    return [FunctionTool(listar_meus_visitantes), FunctionTool(autorizar_visitante, require_confirmation=True)]
