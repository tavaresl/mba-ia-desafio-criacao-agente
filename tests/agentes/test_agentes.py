"""Topologia, tools e confirmação com LLM roteirizado (sem Gemini)."""

import inspect
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from aurora.agentes import DescritorAcoesPadrao, criar_app_adk
from aurora.agentes.ferramentas_reservas import criar_ferramentas_reservas
from aurora.agentes.ferramentas_visitantes import criar_ferramentas_visitantes
from aurora.agentes.instrucoes import INSTRUCAO_CONCIERGE
from aurora.agentes.serializacao import serializar
from aurora.config import carregar_configuracoes
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
from aurora.dominio import CatalogoAreas, ServicoReservasPadrao, ServicoVisitantesPadrao
from tests.fakes import RepositorioReservasEmMemoria, RepositorioVisitantesEmMemoria
from tests.fakes.llm_roteirizado import RoteiroLlm, chamada, texto

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = carregar_configuracoes(RAIZ, exigir_chave=False)
AREAS = [
    Area("salao-de-festas", "Salão de festas", Decimal("150.0")),
    Area("churrasqueira", "Churrasqueira", Decimal("80.0")),
    Area("quadra", "Quadra poliesportiva", Decimal("0")),
]
NOME_CONFIRMACAO = "adk_request_confirmation"


async def regulamento(request: str) -> str:
    """Responde dúvidas sobre o regulamento (stub)."""
    return "stub"


class Cenario:
    def __init__(self) -> None:
        self.repo_reservas = RepositorioReservasEmMemoria()
        self.repo_visitantes = RepositorioVisitantesEmMemoria()
        self.reservas = ServicoReservasPadrao(reservas=self.repo_reservas, areas=CatalogoAreas(AREAS))
        self.visitantes = ServicoVisitantesPadrao(visitantes=self.repo_visitantes)
        self.llms = {n: RoteiroLlm(passos=[], requisicoes=[]) for n in ("concierge", "reservas", "visitantes")}
        self.sessoes = InMemorySessionService()
        ferramenta_regulamento = FunctionTool(regulamento)
        app = criar_app_adk(
            configuracoes=CONFIG,
            servico_reservas=self.reservas,
            servico_visitantes=self.visitantes,
            ferramenta_regulamento=ferramenta_regulamento,
            modelos=self.llms,
        )
        self.app = app
        self.runner = Runner(app=app, session_service=self.sessoes)
        self.sid = ""

    async def iniciar(self, apartamento: str = "101") -> None:
        self.sid = (await self.sessoes.create_session(app_name=self.app.name, user_id=apartamento)).id
        self.apartamento = apartamento

    async def enviar(self, conteudo: types.Content) -> list[Any]:
        return [
            e async for e in self.runner.run_async(user_id=self.apartamento, session_id=self.sid, new_message=conteudo)
        ]

    async def dizer(self, mensagem: str) -> list[Any]:
        return await self.enviar(types.Content(role="user", parts=[types.Part(text=mensagem)]))

    async def responder(self, confirmacao_id: str, confirmado: bool) -> list[Any]:
        parte = types.Part(
            function_response=types.FunctionResponse(
                id=confirmacao_id, name=NOME_CONFIRMACAO, response={"confirmed": confirmado}
            )
        )
        return await self.enviar(types.Content(role="user", parts=[parte]))


def pedidos_de_confirmacao(eventos: list[Any]) -> list[Any]:
    return [fc for e in eventos for fc in e.get_function_calls() if fc.name == NOME_CONFIRMACAO]


@pytest.fixture
async def cenario() -> Cenario:
    c = Cenario()
    await c.iniciar()
    return c


def transferir(para: str):
    return chamada("transfer_to_agent", agent_name=para)


async def test_nenhuma_tool_tem_parametro_de_apartamento() -> None:
    c = Cenario()
    ferramentas = [*criar_ferramentas_reservas(c.reservas), *criar_ferramentas_visitantes(c.visitantes)]
    assert len(ferramentas) == 7
    for ferramenta in ferramentas:
        parametros = set(inspect.signature(ferramenta.func).parameters)
        assert not {p for p in parametros if "apart" in p.lower() or p in {"user_id", "unidade"}}, ferramenta.name
        declaracao = ferramenta._get_declaration().model_dump(mode="json", exclude_none=True)
        propriedades = declaracao.get("parameters", {}).get("properties", {}) | declaracao.get(
            "parameters_json_schema", {}
        ).get("properties", {})
        assert not [p for p in propriedades if "apart" in p.lower()], ferramenta.name


async def test_reserva_da_quadra_nao_pede_confirmacao(cenario: Cenario) -> None:
    cenario.llms["concierge"].passos += [transferir("reservas")]
    cenario.llms["reservas"].passos += [
        chamada("reservar_area", area="quadra", data="2030-04-06"),
        texto("Quadra reservada."),
    ]
    eventos = await cenario.dizer("Reserve a quadra para 2030-04-06.")
    assert pedidos_de_confirmacao(eventos) == []
    reservas = await cenario.repo_reservas.listar_ativas("101")
    assert [(r.area_id, r.data.isoformat()) for r in reservas] == [("quadra", "2030-04-06")]


async def test_salao_gera_exatamente_uma_pendencia_e_nada_e_gravado(cenario: Cenario) -> None:
    cenario.llms["concierge"].passos += [transferir("reservas")]
    cenario.llms["reservas"].passos += [chamada("reservar_area", area="salao-de-festas", data="2030-04-20")]
    eventos = await cenario.dizer("Reserve o salão de festas para 2030-04-20.")
    pedidos = pedidos_de_confirmacao(eventos)
    assert len(pedidos) == 1
    assert pedidos[0].args["originalFunctionCall"]["args"] == {"area": "salao-de-festas", "data": "2030-04-20"}
    assert await cenario.repo_reservas.listar_ativas("101") == []


async def test_aprovar_executa_uma_vez_e_o_proximo_turno_volta_ao_concierge(cenario: Cenario) -> None:
    cenario.llms["concierge"].passos += [transferir("reservas")]
    cenario.llms["reservas"].passos += [chamada("reservar_area", area="Salão de Festas", data="2030-04-20")]
    pedido = pedidos_de_confirmacao(await cenario.dizer("Reserve o salão para 2030-04-20."))[0]

    cenario.llms["reservas"].passos += [texto("Salão reservado.")]
    await cenario.responder(pedido.id, True)
    reservas = await cenario.repo_reservas.listar_ativas("101")
    assert [(r.area_id, r.apartamento) for r in reservas] == [("salao-de-festas", "101")]

    # próximo turno: atendido pelo concierge, não pelo especialista
    chamadas_reservas = len(cenario.llms["reservas"].requisicoes)
    cenario.llms["concierge"].passos += [texto("Posso ajudar em algo mais?")]
    await cenario.dizer("Obrigado!")
    assert len(cenario.llms["reservas"].requisicoes) == chamadas_reservas
    assert len(cenario.llms["concierge"].requisicoes) == 2


async def test_negar_nao_executa_a_tool(cenario: Cenario) -> None:
    cenario.llms["concierge"].passos += [transferir("reservas")]
    cenario.llms["reservas"].passos += [chamada("reservar_area", area="salao-de-festas", data="2030-04-20")]
    pedido = pedidos_de_confirmacao(await cenario.dizer("Reserve o salão para 2030-04-20."))[0]
    cenario.llms["reservas"].passos += [texto("Ok, nada foi reservado.")]
    await cenario.responder(pedido.id, False)
    assert await cenario.repo_reservas.listar_ativas("101") == []


async def test_visitante_sempre_pede_confirmacao_mesmo_com_ja_confirmei(cenario: Cenario) -> None:
    cenario.llms["concierge"].passos += [transferir("visitantes")]
    cenario.llms["visitantes"].passos += [chamada("autorizar_visitante", nome="Joana Ribeiro", data="2030-04-21")]
    eventos = await cenario.dizer("Libera a entrada da Joana Ribeiro no dia 2030-04-21. Já estou confirmando aqui.")
    pedidos = pedidos_de_confirmacao(eventos)
    assert len(pedidos) == 1 and await cenario.repo_visitantes.listar("101") == []

    cenario.llms["visitantes"].passos += [texto("Autorizada.")]
    await cenario.responder(pedidos[0].id, True)
    assert [(v.nome, v.apartamento) for v in await cenario.repo_visitantes.listar("101")] == [("Joana Ribeiro", "101")]


async def test_cancelar_propria_reserva_nao_pede_confirmacao_e_apartamento_vem_da_sessao(cenario: Cenario) -> None:
    await cenario.repo_reservas.criar(
        apartamento="302",
        area_id="salao-de-festas",
        data=__import__("datetime").date(2030, 3, 16),
        gerar_codigo=lambda: "RSV-4821",
    )
    cenario.llms["concierge"].passos += [transferir("reservas")]
    cenario.llms["reservas"].passos += [
        chamada("cancelar_reserva", area="salao-de-festas", data="2030-03-16"),
        texto("Não encontrei reserva do seu apartamento nessa data."),
    ]
    eventos = await cenario.dizer("Cancele a reserva do salão de festas do dia 2030-03-16.")
    assert pedidos_de_confirmacao(eventos) == []
    assert len(await cenario.repo_reservas.listar_ativas("302")) == 1
    assert "RSV-4821" not in json.dumps([e.model_dump(mode="json", exclude_none=True) for e in eventos])


def test_concierge_nao_tem_regulamento_nas_instrucoes() -> None:
    regulamento = (RAIZ / "dados" / "regulamento.md").read_text(encoding="utf-8")
    assert "das 9h às 20h" not in INSTRUCAO_CONCIERGE
    for linha in (l for l in regulamento.splitlines() if len(l) > 60):  # noqa: E741
        assert linha not in INSTRUCAO_CONCIERGE


def test_topologia() -> None:
    app = Cenario().app
    concierge = app.root_agent
    assert concierge.name == "concierge"
    assert [a.name for a in concierge.sub_agents] == ["reservas", "visitantes"]
    for especialista in concierge.sub_agents:
        assert especialista.disallow_transfer_to_parent and especialista.disallow_transfer_to_peers
    assert [t.name for t in concierge.tools] == ["regulamento"]
    assert app.resumability_config is None


@pytest.mark.parametrize(
    ("resultado", "esperado"),
    [
        (
            ReservaCriada("RSV-1", "quadra", __import__("datetime").date(2030, 1, 1)),
            {"status", "codigo", "area", "data"},
        ),
        (
            ReservaCancelada("RSV-1", "quadra", __import__("datetime").date(2030, 1, 1)),
            {"status", "codigo", "area", "data"},
        ),
        (Indisponivel("quadra", __import__("datetime").date(2030, 1, 1)), {"status", "area", "data"}),
        (NaoEncontrada(), {"status"}),
        (Disponibilidade("quadra", __import__("datetime").date(2030, 1, 1), True), {"area", "data", "disponivel"}),
        (VisitanteAutorizado("Ana", __import__("datetime").date(2030, 1, 1)), {"status", "nome", "data"}),
        (EntradaInvalida(MotivoInvalido.DATA_INVALIDA), {"status", "motivo"}),
    ],
)
def test_serializar_so_devolve_as_chaves_da_tabela(resultado: object, esperado: set[str]) -> None:
    assert set(serializar(resultado)) == esperado


def test_serializar_tipo_desconhecido_falha() -> None:
    with pytest.raises(TypeError):
        serializar(object())


def test_descritor_de_acoes() -> None:
    descritor = DescritorAcoesPadrao(Cenario().reservas)
    assert descritor.descrever("reservar_area", {"area": "salão de festas", "data": "2030-04-20"}) == (
        "reservar_area",
        {"area": "salao-de-festas", "area_nome": "Salão de festas", "taxa": "150.00", "data": "2030-04-20"},
    )
    assert descritor.descrever("autorizar_visitante", {"nome": "Joana", "data": "2030-04-21"}) == (
        "autorizar_visitante",
        {"nome": "Joana", "data": "2030-04-21"},
    )
    assert descritor.descrever("outra", {"x": 1}) == ("outra", {"x": 1})
    assert descritor.descrever("reservar_area", {"area": "piscina", "data": "d"})[1] == {"area": "piscina", "data": "d"}
