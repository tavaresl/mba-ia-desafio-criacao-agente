"""Catálogo de dados de referência (áreas e apartamentos)."""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aurora.contratos import Area

__all__ = ["CatalogoReferenciaSqlite"]


class CatalogoReferenciaSqlite:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def listar_areas(self) -> list[Area]:
        async with self._engine.connect() as conexao:
            linhas = await conexao.execute(text("SELECT id, nome, taxa FROM areas ORDER BY id"))
            return [Area(l.id, l.nome, Decimal(str(l.taxa))) for l in linhas]  # noqa: E741

    async def apartamento_existe(self, numero: str) -> bool:
        async with self._engine.connect() as conexao:
            linha = await conexao.execute(text("SELECT 1 FROM apartamentos WHERE numero = :n"), {"n": numero})
            return linha.first() is not None
