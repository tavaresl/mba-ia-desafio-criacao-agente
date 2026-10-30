"""Índice `session_id` → apartamento (ADR-009)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aurora.persistencia._tempo import agora_iso

__all__ = ["IndiceSessoesSqlite"]


class IndiceSessoesSqlite:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def registrar(self, *, session_id: str, apartamento: str) -> None:
        async with self._engine.begin() as conexao:
            await conexao.execute(
                text("INSERT INTO sessoes (session_id, apartamento, criada_em) VALUES (:s, :a, :agora)"),
                {"s": session_id, "a": apartamento, "agora": agora_iso()},
            )

    async def apartamento_de(self, session_id: str) -> str | None:
        async with self._engine.connect() as conexao:
            linha = await conexao.execute(
                text("SELECT apartamento FROM sessoes WHERE session_id = :s"), {"s": session_id}
            )
            registro = linha.first()
            return registro.apartamento if registro else None

    async def remover(self, session_id: str) -> None:
        async with self._engine.begin() as conexao:
            await conexao.execute(text("DELETE FROM sessoes WHERE session_id = :s"), {"s": session_id})

    async def limpar(self) -> None:
        async with self._engine.begin() as conexao:
            await conexao.execute(text("DELETE FROM sessoes"))
