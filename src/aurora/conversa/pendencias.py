"""Pendências de confirmação derivadas dos eventos persistidos (ADR-007)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from google.adk.events import Event

__all__ = ["NOME_CHAMADA_CONFIRMACAO", "PendenciaBruta", "listar_pendencias"]

NOME_CHAMADA_CONFIRMACAO = "adk_request_confirmation"


@dataclass(frozen=True, slots=True)
class PendenciaBruta:
    id: str
    nome_tool: str | None
    argumentos: Mapping[str, Any]


def listar_pendencias(eventos: Sequence[Event]) -> list[PendenciaBruta]:
    """Chamadas `adk_request_confirmation` sem `FunctionResponse` posterior, na ordem em que foram pedidas.

    Função pura: como a fonte é o histórico persistido, as pendências sobrevivem ao reinício, e um `id`
    já respondido, inexistente ou de outra sessão nunca aparece aqui.
    """
    respondidas = {resposta.id for evento in eventos for resposta in evento.get_function_responses() if resposta.id}
    pendentes: list[PendenciaBruta] = []
    for evento in eventos:
        for chamada in evento.get_function_calls():
            if chamada.name != NOME_CHAMADA_CONFIRMACAO or not chamada.id or chamada.id in respondidas:
                continue
            original = (chamada.args or {}).get("originalFunctionCall") or {}
            pendentes.append(
                PendenciaBruta(id=chamada.id, nome_tool=original.get("name"), argumentos=original.get("args") or {})
            )
    return pendentes
