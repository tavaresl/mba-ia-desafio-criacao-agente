"""Montagem do `App` do ADK (sem `ResumabilityConfig`, ADR-006)."""

from collections.abc import Mapping

from google.adk.apps import App
from google.adk.models import BaseLlm
from google.adk.tools import BaseTool

from aurora.agentes.topologia import criar_concierge, criar_especialista_reservas, criar_especialista_visitantes
from aurora.config import Configuracoes
from aurora.contratos import ServicoReservas, ServicoVisitantes
from aurora.infra import criar_modelo

__all__ = ["NOMES_AGENTES", "criar_app_adk"]

NOMES_AGENTES = ("concierge", "reservas", "visitantes")


def criar_app_adk(
    *,
    configuracoes: Configuracoes,
    servico_reservas: ServicoReservas,
    servico_visitantes: ServicoVisitantes,
    ferramenta_regulamento: BaseTool,
    modelos: Mapping[str, BaseLlm] | None = None,
) -> App:
    """Cria o `App` com o `concierge` na raiz.

    Args:
        modelos: Substituição do modelo por nome de agente (usado só em testes com LLM roteirizado).
    """
    modelos = modelos or {}
    padrao = None if all(n in modelos for n in NOMES_AGENTES) else criar_modelo(configuracoes)

    def de(nome: str) -> BaseLlm:
        return modelos.get(nome) or padrao  # type: ignore[return-value]

    especialistas = [
        criar_especialista_reservas(configuracoes=configuracoes, servico=servico_reservas, modelo=de("reservas")),
        criar_especialista_visitantes(configuracoes=configuracoes, servico=servico_visitantes, modelo=de("visitantes")),
    ]
    concierge = criar_concierge(
        configuracoes=configuracoes,
        modelo=de("concierge"),
        especialistas=especialistas,
        ferramenta_regulamento=ferramenta_regulamento,
    )
    return App(name=configuracoes.nome_app, root_agent=concierge)
