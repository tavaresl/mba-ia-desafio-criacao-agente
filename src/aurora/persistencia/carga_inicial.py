"""Esquema e restauração transacional do domínio (ADR-016)."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from aurora.contratos import DadosIniciais
from aurora.persistencia._tempo import agora_iso
from aurora.persistencia.esquema import COMANDOS_ESQUEMA

__all__ = ["RepositorioCargaInicialSqlite"]

_LOG = logging.getLogger(__name__)


class RepositorioCargaInicialSqlite:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def criar_esquema(self) -> None:
        async with self._engine.begin() as conexao:
            for comando in COMANDOS_ESQUEMA:
                await conexao.exec_driver_sql(comando)

    async def seed_aplicado(self) -> bool:
        async with self._engine.connect() as conexao:
            linha = await conexao.execute(text("SELECT 1 FROM metadados WHERE chave = 'seed_aplicado'"))
            return linha.first() is not None

    async def restaurar(self, dados: DadosIniciais) -> None:
        """Volta reservas e visitantes ao estado inicial numa única transação.

        `codigos_reserva` nunca é apagada: códigos já emitidos não são reutilizados (RN-05).
        """
        agora = agora_iso()
        async with self._engine.begin() as c:
            await c.execute(text("DELETE FROM reservas"))
            await c.execute(text("DELETE FROM visitantes"))
            for apt in dados.apartamentos:
                await c.execute(
                    text(
                        "INSERT INTO apartamentos (numero, morador) VALUES (:n, :m) "
                        "ON CONFLICT(numero) DO UPDATE SET morador = excluded.morador"
                    ),
                    {"n": apt.numero, "m": apt.morador},
                )
            for area in dados.areas:
                await c.execute(
                    text(
                        "INSERT INTO areas (id, nome, taxa) VALUES (:i, :n, :t) "
                        "ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, taxa = excluded.taxa"
                    ),
                    {"i": area.id, "n": area.nome, "t": str(area.taxa)},
                )
            for r in dados.reservas:
                await c.execute(
                    text("INSERT INTO codigos_reserva (codigo, emitido_em) VALUES (:c, :a) ON CONFLICT DO NOTHING"),
                    {"c": r.codigo, "a": agora},
                )
                await c.execute(
                    text(
                        "INSERT INTO reservas (codigo, apartamento, area_id, data, status, criada_em) "
                        "VALUES (:c, :ap, :ar, :d, 'ativa', :a)"
                    ),
                    {"c": r.codigo, "ap": r.apartamento, "ar": r.area_id, "d": r.data.isoformat(), "a": agora},
                )
            for v in dados.visitantes:
                await c.execute(
                    text("INSERT INTO visitantes (apartamento, nome, data, criado_em) VALUES (:ap, :n, :d, :a)"),
                    {"ap": v.apartamento, "n": v.nome, "d": v.data.isoformat(), "a": agora},
                )
            await c.execute(
                text(
                    "INSERT INTO metadados (chave, valor) VALUES ('seed_aplicado', :a) "
                    "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor"
                ),
                {"a": agora},
            )
        _LOG.info("restauracao_aplicada reservas=%d visitantes=%d", len(dados.reservas), len(dados.visitantes))
