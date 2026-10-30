"""Topologia de agentes: concierge + especialistas por transferência + regulamento como AgentTool (ADR-003/004)."""

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.tools import BaseTool
from google.genai import types

from aurora.agentes.ferramentas_reservas import criar_ferramentas_reservas
from aurora.agentes.ferramentas_visitantes import criar_ferramentas_visitantes
from aurora.agentes.instrucoes import INSTRUCAO_CONCIERGE, INSTRUCAO_RESERVAS, INSTRUCAO_VISITANTES
from aurora.config import Configuracoes
from aurora.contratos import ServicoReservas, ServicoVisitantes

__all__ = ["criar_concierge", "criar_especialista_reservas", "criar_especialista_visitantes"]

# ADR-004: o especialista nunca transfere de volta; o próximo turno recomeça no concierge.
CONFIG_ESPECIALISTA = {
    "mode": "chat",
    "disallow_transfer_to_parent": True,
    "disallow_transfer_to_peers": True,
}


def _geracao(configuracoes: Configuracoes) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(temperature=configuracoes.temperatura)


def criar_especialista_reservas(*, configuracoes: Configuracoes, servico: ServicoReservas, modelo: BaseLlm) -> LlmAgent:
    return LlmAgent(
        name="reservas",
        description="Reserva e cancela áreas comuns (salão de festas, churrasqueira, quadra) e consulta disponibilidade.",
        model=modelo,
        instruction=INSTRUCAO_RESERVAS,
        tools=criar_ferramentas_reservas(servico),
        generate_content_config=_geracao(configuracoes),
        **CONFIG_ESPECIALISTA,
    )


def criar_especialista_visitantes(
    *, configuracoes: Configuracoes, servico: ServicoVisitantes, modelo: BaseLlm
) -> LlmAgent:
    return LlmAgent(
        name="visitantes",
        description="Autoriza a entrada de visitantes no prédio e lista os visitantes autorizados do morador.",
        model=modelo,
        instruction=INSTRUCAO_VISITANTES,
        tools=criar_ferramentas_visitantes(servico),
        generate_content_config=_geracao(configuracoes),
        **CONFIG_ESPECIALISTA,
    )


def criar_concierge(
    *,
    configuracoes: Configuracoes,
    modelo: BaseLlm,
    especialistas: list[LlmAgent],
    ferramenta_regulamento: BaseTool,
) -> LlmAgent:
    return LlmAgent(
        name="concierge",
        description="Agente principal: classifica o pedido do morador e delega aos especialistas.",
        model=modelo,
        instruction=INSTRUCAO_CONCIERGE,
        tools=[ferramenta_regulamento],
        sub_agents=especialistas,
        generate_content_config=_geracao(configuracoes),
    )
