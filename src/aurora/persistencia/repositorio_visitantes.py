"""Repositório de visitantes sobre SQLite."""

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aurora.contratos import Visitante
from aurora.persistencia._tempo import agora_iso

__all__ = ["RepositorioVisitantesSqlite"]


class RepositorioVisitantesSqlite:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def autorizar(self, *, apartamento: str, nome: str, data: date) -> Visitante:
        async with self._engine.begin() as conexao:
            await conexao.execute(
                text(
                    "INSERT INTO visitantes (apartamento, nome, data, criado_em) "
                    "VALUES (:apartamento, :nome, :data, :agora)"
                ),
                {"apartamento": apartamento, "nome": nome, "data": data.isoformat(), "agora": agora_iso()},
            )
        return Visitante(apartamento, nome, data)

    async def listar(self, apartamento: str) -> list[Visitante]:
        async with self._engine.connect() as conexao:
            linhas = await conexao.execute(
                text("SELECT apartamento, nome, data FROM visitantes WHERE apartamento = :a ORDER BY data, id"),
                {"a": apartamento},
            )
            return [Visitante(l.apartamento, l.nome, date.fromisoformat(l.data)) for l in linhas]  # noqa: E741
