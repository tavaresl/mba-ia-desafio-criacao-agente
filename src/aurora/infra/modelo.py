"""Fábrica do modelo Gemini usado por todos os agentes (ADR-018)."""

from google.adk.models.google_llm import Gemini
from google.genai import types

from aurora.config import Configuracoes

__all__ = ["criar_modelo"]

TENTATIVAS_MODELO = 4
ESPERA_INICIAL_S = 2.0


def criar_modelo(configuracoes: Configuracoes) -> Gemini:
    """Cria o `Gemini` com retentativas e espera crescente para erros transitórios (429/503)."""
    return Gemini(
        model=configuracoes.modelo,
        retry_options=types.HttpRetryOptions(attempts=TENTATIVAS_MODELO, initial_delay=ESPERA_INICIAL_S),
    )
