"""Identidade do morador: o apartamento vem sempre da sessão (G2, ADR-009)."""

from google.adk.tools import ToolContext

__all__ = ["apartamento_da_sessao"]


def apartamento_da_sessao(tool_context: ToolContext) -> str:
    """Devolve o apartamento da sessão (`user_id`, definido uma única vez na criação da sessão).

    Raises:
        RuntimeError: Se o `user_id` estiver vazio (bug de montagem, não de negócio).
    """
    apartamento = tool_context.user_id
    if not apartamento:
        raise RuntimeError("sessão sem apartamento (user_id vazio)")
    return apartamento
