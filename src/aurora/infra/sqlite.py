"""Fábrica de engines SQLite assíncronos com WAL e busy_timeout em toda conexão."""

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

__all__ = ["criar_engine_sqlite"]


def criar_engine_sqlite(caminho: Path, *, busy_timeout_ms: int) -> AsyncEngine:
    """Cria um `AsyncEngine` `sqlite+aiosqlite` com pragmas aplicados a cada conexão nova.

    O modo de transação do driver é desligado (`isolation_level=None`) para que as transações
    sejam controladas explicitamente com `BEGIN IMMEDIATE`, evitando o upgrade de leitura para
    escrita (que falha com `database is locked` sob concorrência).
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(f"sqlite+aiosqlite:///{caminho}", connect_args={"timeout": busy_timeout_ms / 1000})

    @event.listens_for(engine.sync_engine, "connect")
    def _configurar_conexao(dbapi_connection, _registro) -> None:  # noqa: ANN001
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    @event.listens_for(engine.sync_engine, "begin")
    def _iniciar_transacao(conexao) -> None:  # noqa: ANN001
        conexao.exec_driver_sql("BEGIN IMMEDIATE")

    return engine
