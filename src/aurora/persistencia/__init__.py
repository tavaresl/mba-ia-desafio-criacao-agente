"""Persistência do domínio em SQLite (única dona do SQL do domínio)."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from aurora.contratos import (
    CatalogoReferencia,
    IndiceSessoes,
    RepositorioCargaInicial,
    RepositorioReservas,
    RepositorioVisitantes,
)
from aurora.persistencia.carga_inicial import RepositorioCargaInicialSqlite
from aurora.persistencia.catalogo_referencia import CatalogoReferenciaSqlite
from aurora.persistencia.indice_sessoes import IndiceSessoesSqlite
from aurora.persistencia.repositorio_reservas import RepositorioReservasSqlite
from aurora.persistencia.repositorio_visitantes import RepositorioVisitantesSqlite

__all__ = [
    "CatalogoReferenciaSqlite",
    "IndiceSessoesSqlite",
    "RepositorioCargaInicialSqlite",
    "RepositorioReservasSqlite",
    "RepositorioVisitantesSqlite",
    "Repositorios",
    "criar_repositorios",
]


@dataclass(frozen=True, slots=True)
class Repositorios:
    reservas: RepositorioReservas
    visitantes: RepositorioVisitantes
    referencia: CatalogoReferencia
    sessoes: IndiceSessoes
    carga: RepositorioCargaInicial


def criar_repositorios(engine: AsyncEngine) -> Repositorios:
    """Monta os repositórios SQLite sobre um engine criado por `criar_engine_sqlite`."""
    return Repositorios(
        reservas=RepositorioReservasSqlite(engine),
        visitantes=RepositorioVisitantesSqlite(engine),
        referencia=CatalogoReferenciaSqlite(engine),
        sessoes=IndiceSessoesSqlite(engine),
        carga=RepositorioCargaInicialSqlite(engine),
    )
