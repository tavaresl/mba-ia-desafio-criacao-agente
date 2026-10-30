"""Infraestrutura compartilhada: engine SQLite, modelo Gemini e logs."""

from aurora.infra.logs import configurar_logs
from aurora.infra.modelo import criar_modelo
from aurora.infra.sqlite import criar_engine_sqlite

__all__ = ["configurar_logs", "criar_engine_sqlite", "criar_modelo"]
