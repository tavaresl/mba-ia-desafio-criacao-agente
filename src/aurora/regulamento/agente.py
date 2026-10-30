"""Especialista de regulamento, exposto como `AgentTool` (ADR-003, ADR-015).

O `AgentTool` executa o especialista numa sessão em memória descartada: o texto do capítulo consultado
nunca entra na sessão principal; só a resposta final entra (G4).
"""

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm
from google.adk.tools import AgentTool, BaseTool
from google.genai import types

from aurora.config import Configuracoes
from aurora.infra import criar_modelo
from aurora.regulamento.ferramenta_capitulo import criar_ferramenta_capitulo
from aurora.regulamento.indice import IndiceRegulamento
from aurora.regulamento.instrucoes import montar_instrucoes

__all__ = ["NOME_FERRAMENTA", "criar_especialista_regulamento", "criar_ferramenta_regulamento"]

NOME_FERRAMENTA = "regulamento"
DESCRICAO = (
    "Responde dúvidas sobre o regulamento interno do condomínio (horários, uso das áreas comuns, "
    "regras de convivência). Envie a pergunta do morador."
)


def criar_especialista_regulamento(
    *, configuracoes: Configuracoes, indice: IndiceRegulamento, modelo: BaseLlm | None = None
) -> LlmAgent:
    return LlmAgent(
        name=NOME_FERRAMENTA,
        description=DESCRICAO,
        model=modelo or criar_modelo(configuracoes),
        instruction=montar_instrucoes(indice),
        tools=[criar_ferramenta_capitulo(indice)],
        generate_content_config=types.GenerateContentConfig(temperature=configuracoes.temperatura),
    )


def criar_ferramenta_regulamento(
    *, configuracoes: Configuracoes, indice: IndiceRegulamento | None = None, modelo: BaseLlm | None = None
) -> BaseTool:
    """Devolve o `AgentTool` do especialista. Contrato consumido pelo FDD-06 (`modelo` é só para testes)."""
    indice = indice or IndiceRegulamento.carregar(configuracoes.diretorio_dados / "regulamento.md")
    return AgentTool(agent=criar_especialista_regulamento(configuracoes=configuracoes, indice=indice, modelo=modelo))
