"""Contrato HTTP com fakes: sem ADK e sem banco."""

import ast
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import httpx
import pytest

from aurora.api import Aplicacao, criar_app_http
from aurora.contratos import ModeloIndisponivel, Reserva, Visitante
from tests.fakes import ServicoConversaFalso, ServicoReservasFalso, ServicoVisitantesFalso


async def _fechar() -> None:
    return None


@pytest.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    async def montar() -> Aplicacao:
        return Aplicacao(
            conversa=ServicoConversaFalso(),
            reservas=ServicoReservasFalso([Reserva("RSV-1377", "101", "quadra", date(2030, 3, 9))]),
            visitantes=ServicoVisitantesFalso([Visitante("302", "Marina Duarte", date(2030, 3, 16))]),
            fechar=_fechar,
        )

    app = criar_app_http(montar)
    async with app.router.lifespan_context(app):
        transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transporte, base_url="http://teste") as c:
            yield c


async def test_fluxo_de_conversa_e_confirmacao(cliente: httpx.AsyncClient) -> None:
    criada = await cliente.post("/sessoes", json={"apartamento": "101"})
    assert criada.status_code == 201
    sid = criada.json()["session_id"]

    msg = await cliente.post(f"/sessoes/{sid}/mensagens", json={"texto": "Reserve o salão"})
    assert msg.status_code == 200
    corpo = msg.json()
    assert corpo["resposta"] == "" and set(corpo) == {"resposta", "confirmacoes_pendentes"}
    (pendente,) = corpo["confirmacoes_pendentes"]
    assert set(pendente) == {"id", "acao", "detalhes"}

    ok = await cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": pendente["id"], "confirmado": True})
    assert ok.status_code == 200 and ok.json() == {"resposta": "ok", "confirmacoes_pendentes": []}

    repetido = await cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": pendente["id"], "confirmado": True})
    assert repetido.status_code == 409
    inexistente = await cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": "id-inexistente", "confirmado": True})
    assert inexistente.status_code == 409


async def test_eventos_em_ordem(cliente: httpx.AsyncClient) -> None:
    sid = (await cliente.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
    await cliente.post(f"/sessoes/{sid}/mensagens", json={"texto": "um"})
    await cliente.post(f"/sessoes/{sid}/mensagens", json={"texto": "dois"})
    resposta = await cliente.get(f"/sessoes/{sid}/eventos")
    assert resposta.status_code == 200 and [e["texto"] for e in resposta.json()] == ["um", "dois"]


@pytest.mark.parametrize(
    ("metodo", "rota", "corpo"),
    [
        ("GET", "/sessoes/sessao-inexistente/eventos", None),
        ("POST", "/sessoes/sessao-inexistente/mensagens", {"texto": "oi"}),
        ("POST", "/sessoes/sessao-inexistente/confirmacoes", {"id": "x", "confirmado": True}),
    ],
)
async def test_sessao_inexistente_da_404(
    cliente: httpx.AsyncClient, metodo: str, rota: str, corpo: dict | None
) -> None:
    resposta = await cliente.request(metodo, rota, json=corpo)
    assert resposta.status_code == 404 and resposta.json() == {"detail": "sessão não encontrada"}


async def test_corpo_invalido_da_422(cliente: httpx.AsyncClient) -> None:
    assert (await cliente.post("/sessoes", json={})).status_code == 422
    sid = (await cliente.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
    assert (await cliente.post(f"/sessoes/{sid}/confirmacoes", json={"id": "x"})).status_code == 422


async def test_rotas_de_verificacao(cliente: httpx.AsyncClient) -> None:
    reservas = await cliente.get("/apartamentos/101/reservas")
    assert reservas.status_code == 200
    assert reservas.json() == [{"codigo": "RSV-1377", "area": "quadra", "data": "2030-03-09"}]
    visitantes = await cliente.get("/apartamentos/302/visitantes")
    assert visitantes.json() == [{"nome": "Marina Duarte", "data": "2030-03-16"}]
    assert (await cliente.get("/apartamentos/101/visitantes")).json() == []


async def test_erros_de_aplicacao_e_inesperados_com_corpo_generico() -> None:
    class ConversaQuebrada(ServicoConversaFalso):
        async def criar_sessao(self, apartamento: str) -> str:
            if apartamento == "modelo":
                raise ModeloIndisponivel
            raise RuntimeError("detalhe interno: SELECT * FROM reservas")

    async def montar() -> Aplicacao:
        return Aplicacao(ConversaQuebrada(), ServicoReservasFalso(), ServicoVisitantesFalso(), _fechar)

    app = criar_app_http(montar)
    async with app.router.lifespan_context(app):
        transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transporte, base_url="http://teste") as c:
            modelo = await c.post("/sessoes", json={"apartamento": "modelo"})
            assert modelo.status_code == 503 and "SELECT" not in modelo.text
            interno = await c.post("/sessoes", json={"apartamento": "x"})
            assert interno.status_code == 500 and interno.json() == {"detail": "erro interno"}


def test_rotas_so_importam_contratos() -> None:
    api = Path(__file__).resolve().parents[2] / "src" / "aurora" / "api"
    for arquivo in api.glob("rotas_*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text())):
            modulo = no.module if isinstance(no, ast.ImportFrom) else None
            if modulo and modulo.startswith("aurora."):
                assert modulo in {"aurora.contratos", "aurora.api.esquemas"}, f"{arquivo.name} importa {modulo}"
