"""Serialização completa dos eventos da sessão."""

from collections.abc import Sequence
from typing import Any

from google.adk.events import Event

__all__ = ["serializar_eventos"]


def serializar_eventos(eventos: Sequence[Event]) -> list[dict[str, Any]]:
    """Eventos completos (chamadas e respostas de tool incluídas), na ordem gravada."""
    return [evento.model_dump(mode="json", by_alias=True, exclude_none=True) for evento in eventos]
