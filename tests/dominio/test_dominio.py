import re
from datetime import date
from decimal import Decimal

import pytest

from aurora.contratos import (
    Area,
    Disponibilidade,
    EntradaInvalida,
    Indisponivel,
    MotivoInvalido,
    NaoEncontrada,
    ReservaCancelada,
    ReservaCriada,
    VisitanteAutorizado,
)
from aurora.dominio import (
    CatalogoAreas,
    ServicoReservasPadrao,
    ServicoVisitantesPadrao,
    gerar_codigo_reserva,
    interpretar_data,
    normalizar_nome_visitante,
)
from tests.fakes import RepositorioReservasEmMemoria, RepositorioVisitantesEmMemoria

AREAS = [
    Area("salao-de-festas", "Salão de festas", Decimal("150.0")),
    Area("churrasqueira", "Churrasqueira", Decimal("80.0")),
    Area("quadra", "Quadra poliesportiva", Decimal("0")),
]


@pytest.fixture
def servico() -> ServicoReservasPadrao:
    return ServicoReservasPadrao(reservas=RepositorioReservasEmMemoria(), areas=CatalogoAreas(AREAS))


@pytest.mark.parametrize("texto", ["quadra", "Quadra", "QUADRA poliesportiva", "  quadra  "])
def test_quadra_dispensa_confirmacao(texto: str) -> None:
    assert CatalogoAreas(AREAS).exige_confirmacao(texto) is False


@pytest.mark.parametrize(
    "texto", ["salao-de-festas", "Salão de Festas", "salao de festas", "churrasqueira", "piscina", ""]
)
def test_demais_exigem_confirmacao_fail_closed(texto: str) -> None:
    assert CatalogoAreas(AREAS).exige_confirmacao(texto) is True


def test_resolver_nao_faz_fuzzy() -> None:
    catalogo = CatalogoAreas(AREAS)
    assert catalogo.resolver("salão") is None
    assert catalogo.resolver("Salão de festas").id == "salao-de-festas"


@pytest.mark.parametrize("texto", ["2030-02-30", "20/04/2030", "2030-4-2", "", None, "amanhã"])
def test_datas_invalidas(texto: str | None) -> None:
    assert interpretar_data(texto) is None


def test_data_valida() -> None:
    assert interpretar_data("2030-04-20") == date(2030, 4, 20)


@pytest.mark.parametrize("nome", ["", "   ", "x" * 101, "Joana\x00", None])
def test_nomes_invalidos(nome: str | None) -> None:
    assert normalizar_nome_visitante(nome) is None


def test_nome_valido_com_acento() -> None:
    assert normalizar_nome_visitante("  José   da Silva ") == "José da Silva"


def test_codigo_segue_formato_e_nao_colide_com_iniciais() -> None:
    iniciais = {"RSV-1377", "RSV-4821", "RSV-2950"}
    for _ in range(500):
        codigo = gerar_codigo_reserva()
        assert re.fullmatch(r"RSV-[0-9A-HJKMNP-TV-Z]{6}", codigo)
        assert codigo not in iniciais


async def test_reservar_data_ocupada_nao_revela_ocupante(servico: ServicoReservasPadrao) -> None:
    await servico.reservar(apartamento="302", area="salão de festas", data="2030-03-16")
    resultado = await servico.reservar(apartamento="101", area="salao-de-festas", data="2030-03-16")
    assert resultado == Indisponivel("salao-de-festas", date(2030, 3, 16))
    assert "302" not in repr(resultado)


async def test_reservar_entradas_invalidas(servico: ServicoReservasPadrao) -> None:
    assert await servico.reservar(apartamento="101", area="piscina", data="2030-01-01") == EntradaInvalida(
        MotivoInvalido.AREA_INEXISTENTE
    )
    assert await servico.reservar(apartamento="101", area="quadra", data="2030-02-30") == EntradaInvalida(
        MotivoInvalido.DATA_INVALIDA
    )


async def test_disponibilidade_so_livre_ou_ocupada(servico: ServicoReservasPadrao) -> None:
    await servico.reservar(apartamento="302", area="quadra", data="2030-03-16")
    assert await servico.consultar_disponibilidade(area="quadra", data="2030-03-16") == Disponibilidade(
        "quadra", date(2030, 3, 16), False
    )
    assert (await servico.consultar_disponibilidade(area="quadra", data="2030-03-17")).disponivel is True


async def test_cancelar_de_terceiro_nao_altera_nada(servico: ServicoReservasPadrao) -> None:
    criada = await servico.reservar(apartamento="302", area="salao-de-festas", data="2030-03-16")
    assert isinstance(criada, ReservaCriada)
    assert await servico.cancelar(apartamento="101", area="salão de festas", data="2030-03-16") == NaoEncontrada()
    assert await servico.cancelar(apartamento="101", codigo=criada.codigo.lower()) == NaoEncontrada()
    assert len(await servico.listar_do_apartamento("302")) == 1
    assert len(await servico.listar_do_apartamento("101")) == 0


async def test_cancelar_propria_por_area_data_e_por_codigo(servico: ServicoReservasPadrao) -> None:
    await servico.reservar(apartamento="101", area="quadra", data="2030-03-09")
    assert isinstance(await servico.cancelar(apartamento="101", area="quadra", data="2030-03-09"), ReservaCancelada)
    criada = await servico.reservar(apartamento="101", area="quadra", data="2030-03-09")
    assert isinstance(await servico.cancelar(apartamento="101", codigo=f" {criada.codigo.lower()} "), ReservaCancelada)


async def test_cancelar_sem_identificacao(servico: ServicoReservasPadrao) -> None:
    assert await servico.cancelar(apartamento="101", area="quadra") == EntradaInvalida(
        MotivoInvalido.IDENTIFICACAO_INCOMPLETA
    )


async def test_visitantes() -> None:
    repo = RepositorioVisitantesEmMemoria()
    servico = ServicoVisitantesPadrao(visitantes=repo)
    assert await servico.autorizar(
        apartamento="101", nome=" Joana  Ribeiro ", data="2030-04-21"
    ) == VisitanteAutorizado("Joana Ribeiro", date(2030, 4, 21))
    assert await servico.autorizar(apartamento="101", nome="", data="2030-04-21") == EntradaInvalida(
        MotivoInvalido.NOME_INVALIDO
    )
    assert await servico.autorizar(apartamento="101", nome="Ana", data="x") == EntradaInvalida(
        MotivoInvalido.DATA_INVALIDA
    )
    assert [v.nome for v in await servico.listar_do_apartamento("101")] == ["Joana Ribeiro"]
    assert await servico.listar_do_apartamento("302") == []
