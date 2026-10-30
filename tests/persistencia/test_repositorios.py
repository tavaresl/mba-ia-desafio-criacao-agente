"""Suíte de contrato: roda contra o fake em memória e contra a implementação SQLite."""

import asyncio
import itertools
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aurora.contratos import (
    Apartamento,
    Area,
    DadosIniciais,
    Indisponivel,
    NaoEncontrada,
    Reserva,
    ReservaCancelada,
    ReservaCriada,
    Visitante,
)
from aurora.infra import criar_engine_sqlite
from aurora.persistencia import criar_repositorios
from tests.fakes import RepositorioReservasEmMemoria, RepositorioVisitantesEmMemoria

SALAO = "salao-de-festas"
DADOS = DadosIniciais(
    apartamentos=(Apartamento("101", "Helena"), Apartamento("302", "Rafael")),
    areas=(Area(SALAO, "Salão de festas", Decimal("150.0")), Area("quadra", "Quadra", Decimal("0"))),
    reservas=(
        Reserva("RSV-1377", "101", "quadra", date(2030, 3, 9)),
        Reserva("RSV-4821", "302", SALAO, date(2030, 3, 16)),
    ),
    visitantes=(Visitante("302", "Marina Duarte", date(2030, 3, 16)),),
)


def gerador(prefixo: str = "T"):
    contador = itertools.count(1)
    return lambda: f"{prefixo}-{next(contador)}"


@pytest.fixture(params=["fake", "sqlite"])
async def reservas(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "fake":
        yield RepositorioReservasEmMemoria()
        return
    engine = criar_engine_sqlite(tmp_path / "d.db", busy_timeout_ms=10000)
    repos = criar_repositorios(engine)
    await repos.carga.criar_esquema()
    await repos.carga.restaurar(DADOS)
    yield repos.reservas
    await engine.dispose()


@pytest.fixture
async def sqlite(tmp_path: Path):
    engine = criar_engine_sqlite(tmp_path / "d.db", busy_timeout_ms=10000)
    repos = criar_repositorios(engine)
    await repos.carga.criar_esquema()
    await repos.carga.restaurar(DADOS)
    yield repos
    await engine.dispose()


async def test_segunda_reserva_na_mesma_data_e_indisponivel(reservas) -> None:
    primeira = await reservas.criar(apartamento="101", area_id=SALAO, data=date(2030, 4, 20), gerar_codigo=gerador())
    segunda = await reservas.criar(apartamento="302", area_id=SALAO, data=date(2030, 4, 20), gerar_codigo=gerador("U"))
    assert isinstance(primeira, ReservaCriada)
    assert segunda == Indisponivel(SALAO, date(2030, 4, 20))


async def test_cancelar_e_reservar_de_novo(reservas) -> None:
    await reservas.criar(apartamento="101", area_id=SALAO, data=date(2030, 4, 20), gerar_codigo=gerador())
    cancelada = await reservas.cancelar_ativa(apartamento="101", area_id=SALAO, data=date(2030, 4, 20))
    assert isinstance(cancelada, ReservaCancelada)
    nova = await reservas.criar(apartamento="302", area_id=SALAO, data=date(2030, 4, 20), gerar_codigo=gerador("N"))
    assert isinstance(nova, ReservaCriada)


async def test_reserva_de_terceiro_nao_e_cancelada(reservas) -> None:
    antes = await reservas.criar(apartamento="302", area_id=SALAO, data=date(2030, 5, 1), gerar_codigo=gerador())
    assert await reservas.cancelar_ativa(apartamento="101", area_id=SALAO, data=date(2030, 5, 1)) == NaoEncontrada()
    assert await reservas.cancelar_por_codigo(apartamento="101", codigo=antes.codigo) == NaoEncontrada()
    assert await reservas.esta_ocupada(area_id=SALAO, data=date(2030, 5, 1))


async def test_listar_ativas_so_do_apartamento(reservas) -> None:
    await reservas.criar(apartamento="101", area_id="quadra", data=date(2030, 6, 2), gerar_codigo=gerador("A"))
    await reservas.criar(apartamento="302", area_id="quadra", data=date(2030, 6, 3), gerar_codigo=gerador("B"))
    assert [r.apartamento for r in await reservas.listar_ativas("101")] == ["101"] * len(
        await reservas.listar_ativas("101")
    )
    assert all(r.apartamento == "302" for r in await reservas.listar_ativas("302"))


async def test_visitantes_fake_lista_ordenado() -> None:
    repo = RepositorioVisitantesEmMemoria()
    await repo.autorizar(apartamento="101", nome="B", data=date(2030, 2, 1))
    await repo.autorizar(apartamento="101", nome="A", data=date(2030, 1, 1))
    assert [v.nome for v in await repo.listar("101")] == ["A", "B"]


async def test_concorrencia_20_chamadas_geram_uma_reserva(sqlite) -> None:
    resultados = await asyncio.gather(
        *(
            sqlite.reservas.criar(
                apartamento="101", area_id=SALAO, data=date(2030, 5, 11), gerar_codigo=gerador(f"C{i}")
            )
            for i in range(20)
        )
    )
    assert sum(isinstance(r, ReservaCriada) for r in resultados) == 1
    assert sum(isinstance(r, Indisponivel) for r in resultados) == 19


async def test_codigo_colidente_gera_outro_e_indisponivel_nao_emite_codigo(sqlite) -> None:
    sequencia = iter(["RSV-1377", "RSV-4821", "NOVO-1"])
    criada = await sqlite.reservas.criar(
        apartamento="101", area_id=SALAO, data=date(2030, 7, 1), gerar_codigo=lambda: next(sequencia)
    )
    assert criada.codigo == "NOVO-1"
    # reserva indisponível desfaz a emissão do código (rollback)
    await sqlite.reservas.criar(
        apartamento="101", area_id=SALAO, data=date(2030, 7, 1), gerar_codigo=lambda: "NAO-EMITIDO"
    )
    outra = await sqlite.reservas.criar(
        apartamento="101", area_id=SALAO, data=date(2030, 7, 2), gerar_codigo=lambda: "NAO-EMITIDO"
    )
    assert outra.codigo == "NAO-EMITIDO"


async def test_codigos_esgotados_levantam_runtime_error(sqlite) -> None:
    with pytest.raises(RuntimeError):
        await sqlite.reservas.criar(
            apartamento="101", area_id=SALAO, data=date(2030, 7, 1), gerar_codigo=lambda: "RSV-1377"
        )


async def test_restaurar_preserva_codigos_e_volta_ao_estado_inicial(sqlite) -> None:
    await sqlite.reservas.criar(apartamento="101", area_id=SALAO, data=date(2030, 8, 1), gerar_codigo=lambda: "NOVO-9")
    await sqlite.visitantes.autorizar(apartamento="101", nome="Joana", data=date(2030, 8, 2))
    await sqlite.carga.restaurar(DADOS)
    assert [r.codigo for r in await sqlite.reservas.listar_ativas("101")] == ["RSV-1377"]
    assert await sqlite.visitantes.listar("101") == []
    assert [v.nome for v in await sqlite.visitantes.listar("302")] == ["Marina Duarte"]
    with pytest.raises(RuntimeError):  # NOVO-9 continua registrado
        await sqlite.reservas.criar(
            apartamento="101", area_id="quadra", data=date(2030, 9, 1), gerar_codigo=lambda: "NOVO-9"
        )


async def test_esquema_idempotente_e_seed_marcado(sqlite) -> None:
    await sqlite.carga.criar_esquema()
    assert await sqlite.carga.seed_aplicado()
    assert len(await sqlite.reservas.listar_ativas("302")) == 1


async def test_catalogo_e_indice_de_sessoes(sqlite) -> None:
    assert await sqlite.referencia.apartamento_existe("101")
    assert not await sqlite.referencia.apartamento_existe("999")
    assert {a.id: a.taxa for a in await sqlite.referencia.listar_areas()}["quadra"] == Decimal("0")
    await sqlite.sessoes.registrar(session_id="s1", apartamento="101")
    assert await sqlite.sessoes.apartamento_de("s1") == "101"
    assert await sqlite.sessoes.apartamento_de("nada") is None
    await sqlite.sessoes.limpar()
    assert await sqlite.sessoes.apartamento_de("s1") is None
