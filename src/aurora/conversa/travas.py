"""Travas assíncronas por sessão (ADR-017)."""

import asyncio

__all__ = ["TravasPorSessao"]


class TravasPorSessao:
    """Serializa as operações da mesma sessão; sessões diferentes correm em paralelo.

    Vale para processo único (decisão do ADR-017): o loop é single-thread, então criar a trava é seguro.
    """

    def __init__(self) -> None:
        self._travas: dict[str, asyncio.Lock] = {}

    def de(self, session_id: str) -> asyncio.Lock:
        trava = self._travas.get(session_id)
        if trava is None:
            trava = self._travas[session_id] = asyncio.Lock()
        return trava
