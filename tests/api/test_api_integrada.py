"""API real (montagem completa, SQLite em disco) com LLM roteirizado: contrato e reinício."""

import dataclasses
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from aurora.api import criar_app_http, montar_aplicacao
from aurora.config import carregar_configuracoes
from tests.fakes.llm_roteirizado import RoteiroLlm, chamada, texto

RAIZ = Path(__file__).resolve().parents[2]


class Servidor:
    def __init__(self, tmp_path: Path) -> None:
        base = carregar_configuracoes(RAIZ, exigir_chave=False)
        self.config = dataclasses.replace(
            base, banco_dominio=tmp_path / "aurora.db", banco_sessoes=tmp_path / "sessions.db"
        )
        self.llms = {n: RoteiroLlm(passos=[], requisicoes=[]) for n in ("concierge", "reservas", "visitantes")}

    async def subir(self) -> AsyncIterator[httpx.AsyncClient]:
        app = criar_app_http(lambda: montar_aplicacao(self.config, modelos=self.llms))
        async with app.router.lifespan_context(app):
            transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transporte, base_url="http://teste") as c:
                yield c


@pytest.fixture
def servidor(tmp_path: Path) -> Servidor:
    return Servidor(tmp_path)


async def test_dados_iniciais_apos_subida_limpa(servidor: Servidor) -> None:
    async for c in servidor.subir():
        assert (await c.get("/apartamentos/101/reservas")).json() == [
            {"codigo": "RSV-1377", "area": "quadra", "data": "2030-03-09"}
        ]
        assert (await c.get("/apartamentos/302/visitantes")).json() == [{"nome": "Marina Duarte", "data": "2030-03-16"}]


async def test_fluxo_http_com_reinicio_sem_restaurar(servidor: Servidor) -> None:
    llms = servidor.llms
    async for c in servidor.subir():
        sid = (await c.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        llms["concierge"].passos += [chamada("transfer_to_agent", agent_name="reservas")]
        llms["reservas"].passos += [chamada("reservar_area", area="salao-de-festas", data="2030-04-20")]
        corpo = (await c.post(f"/sessoes/{sid}/mensagens", json={"texto": "Reserve o salão para 2030-04-20"})).json()
        (pendente,) = corpo["confirmacoes_pendentes"]
        assert pendente["detalhes"]["area"] == "salao-de-festas" and pendente["detalhes"]["data"] == "2030-04-20"
        llms["reservas"].passos += [texto("Reservado.")]
        ok = await c.post(f"/sessoes/{sid}/confirmacoes", json={"id": pendente["id"], "confirmado": True})
        assert ok.status_code == 200 and ok.json()["resposta"] == "Reservado."
        eventos_antes = len((await c.get(f"/sessoes/{sid}/eventos")).json())
        assert eventos_antes > 0

    async for c in servidor.subir():  # reinício, sem restaurar
        reservas = (await c.get("/apartamentos/101/reservas")).json()
        assert [(r["area"], r["data"]) for r in reservas] == [
            ("quadra", "2030-03-09"),
            ("salao-de-festas", "2030-04-20"),
        ]
        assert len((await c.get(f"/sessoes/{sid}/eventos")).json()) == eventos_antes
        repetido = await c.post(f"/sessoes/{sid}/confirmacoes", json={"id": pendente["id"], "confirmado": True})
        assert repetido.status_code == 409
        llms["concierge"].passos += [texto("Você tem a quadra e o salão.")]
        nova = await c.post(f"/sessoes/{sid}/mensagens", json={"texto": "Quais são as minhas reservas agora?"})
        assert nova.status_code == 200
        assert len((await c.get(f"/sessoes/{sid}/eventos")).json()) > eventos_antes
        assert (await c.post("/sessoes/outra/mensagens", json={"texto": "oi"})).status_code == 404
