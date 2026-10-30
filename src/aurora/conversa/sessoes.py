"""Serviço de sessões do ADK sobre SQLite próprio (ADR-011)."""

from google.adk.sessions import DatabaseSessionService

from aurora.config import Configuracoes
from aurora.infra import criar_engine_sqlite

__all__ = ["criar_servico_sessao"]


def criar_servico_sessao(configuracoes: Configuracoes) -> DatabaseSessionService:
    """Cria o `DatabaseSessionService` com engine próprio (WAL e `busy_timeout`).

    O serviço não é dono do engine: quem o cria o encerra com `await servico.db_engine.dispose()`.
    """
    engine = criar_engine_sqlite(configuracoes.banco_sessoes, busy_timeout_ms=configuracoes.sqlite_busy_timeout_ms)
    return DatabaseSessionService(db_engine=engine)
