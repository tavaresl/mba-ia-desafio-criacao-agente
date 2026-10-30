"""Tool `consultar_capitulo`: devolve o texto de um único capítulo, escolhido de um conjunto fechado."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from google.adk.tools import FunctionTool

from aurora.regulamento.indice import IndiceRegulamento

__all__ = ["criar_ferramenta_capitulo"]

_LOG = logging.getLogger(__name__)


def criar_ferramenta_capitulo(indice: IndiceRegulamento) -> FunctionTool:
    """Cria a tool com o parâmetro `capitulo` restrito (enum) aos ids do índice."""

    async def consultar_capitulo(capitulo: str) -> dict[str, Any]:
        """Devolve o texto completo de UM capítulo do regulamento interno.

        Args:
            capitulo: Identificador do capítulo, escolhido da lista de capítulos das instruções.
        """
        encontrado = indice.obter(capitulo)
        if encontrado is None:
            return {"erro": "capitulo_inexistente"}
        _LOG.info("regulamento_consultado capitulo=%s", encontrado.id)
        return {"capitulo": encontrado.id, "titulo": encontrado.titulo, "texto": encontrado.texto}

    ids = tuple(c.id for c in indice.capitulos())
    consultar_capitulo.__annotations__["capitulo"] = Literal[ids]  # type: ignore[valid-type]
    funcao: Callable[[str], Awaitable[dict[str, Any]]] = consultar_capitulo
    return FunctionTool(funcao)
