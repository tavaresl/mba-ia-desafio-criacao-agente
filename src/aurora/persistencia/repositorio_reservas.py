"""Repositório de reservas sobre SQLite (ADR-012, ADR-013, ADR-014)."""

import logging
from collections.abc import Callable
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from aurora.contratos import Indisponivel, NaoEncontrada, Reserva, ReservaCancelada, ReservaCriada
from aurora.persistencia._tempo import agora_iso

__all__ = ["MAX_TENTATIVAS_CODIGO", "RepositorioReservasSqlite"]

MAX_TENTATIVAS_CODIGO = 5
_LOG = logging.getLogger(__name__)


class _AreaDataOcupada(Exception):
    """Sinaliza a violação de `ux_reserva_ativa` para desfazer a transação."""


class RepositorioReservasSqlite:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def criar(
        self, *, apartamento: str, area_id: str, data: date, gerar_codigo: Callable[[], str]
    ) -> ReservaCriada | Indisponivel:
        """Grava a reserva e o código emitido na mesma transação; conflito vira `Indisponivel`."""
        try:
            async with self._engine.begin() as conexao:
                codigo = await self._emitir_codigo(conexao, gerar_codigo)
                try:
                    await conexao.execute(
                        text(
                            "INSERT INTO reservas (codigo, apartamento, area_id, data, status, criada_em) "
                            "VALUES (:codigo, :apartamento, :area_id, :data, 'ativa', :agora)"
                        ),
                        {
                            "codigo": codigo,
                            "apartamento": apartamento,
                            "area_id": area_id,
                            "data": data.isoformat(),
                            "agora": agora_iso(),
                        },
                    )
                except IntegrityError as erro:
                    if "reservas.area_id" in str(erro.orig):
                        raise _AreaDataOcupada from erro
                    raise
        except _AreaDataOcupada:
            _LOG.info("reserva_indisponivel area_id=%s data=%s", area_id, data)
            return Indisponivel(area_id, data)
        _LOG.info("reserva_criada codigo=%s area_id=%s data=%s", codigo, area_id, data)
        return ReservaCriada(codigo, area_id, data)

    @staticmethod
    async def _emitir_codigo(conexao, gerar_codigo: Callable[[], str]) -> str:  # noqa: ANN001
        for _ in range(MAX_TENTATIVAS_CODIGO):
            codigo = gerar_codigo()
            try:
                async with conexao.begin_nested():
                    await conexao.execute(
                        text("INSERT INTO codigos_reserva (codigo, emitido_em) VALUES (:c, :agora)"),
                        {"c": codigo, "agora": agora_iso()},
                    )
            except IntegrityError:
                continue
            return codigo
        raise RuntimeError("não foi possível gerar um código de reserva único")

    async def _cancelar(self, filtro: str, parametros: dict[str, str]) -> ReservaCancelada | NaoEncontrada:
        async with self._engine.begin() as conexao:
            resultado = await conexao.execute(
                text(
                    "UPDATE reservas SET status = 'cancelada', cancelada_em = :agora "
                    f"WHERE apartamento = :apartamento AND status = 'ativa' AND {filtro} "
                    "RETURNING codigo, area_id, data"
                ),
                {"agora": agora_iso(), **parametros},
            )
            linha = resultado.first()
        if linha is None:
            return NaoEncontrada()
        return ReservaCancelada(linha.codigo, linha.area_id, date.fromisoformat(linha.data))

    async def cancelar_ativa(self, *, apartamento: str, area_id: str, data: date) -> ReservaCancelada | NaoEncontrada:
        return await self._cancelar(
            "area_id = :area_id AND data = :data",
            {"apartamento": apartamento, "area_id": area_id, "data": data.isoformat()},
        )

    async def cancelar_por_codigo(self, *, apartamento: str, codigo: str) -> ReservaCancelada | NaoEncontrada:
        return await self._cancelar("codigo = :codigo", {"apartamento": apartamento, "codigo": codigo})

    async def listar_ativas(self, apartamento: str) -> list[Reserva]:
        async with self._engine.connect() as conexao:
            linhas = await conexao.execute(
                text(
                    "SELECT codigo, apartamento, area_id, data FROM reservas "
                    "WHERE apartamento = :a AND status = 'ativa' ORDER BY data, codigo"
                ),
                {"a": apartamento},
            )
            return [
                Reserva(l.codigo, l.apartamento, l.area_id, date.fromisoformat(l.data))
                for l in linhas  # noqa: E741
            ]

    async def esta_ocupada(self, *, area_id: str, data: date) -> bool:
        async with self._engine.connect() as conexao:
            linha = await conexao.execute(
                text("SELECT 1 FROM reservas WHERE area_id = :a AND data = :d AND status = 'ativa' LIMIT 1"),
                {"a": area_id, "d": data.isoformat()},
            )
            return linha.first() is not None
