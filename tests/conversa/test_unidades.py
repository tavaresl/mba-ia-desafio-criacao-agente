import asyncio

from google.adk.events import Event
from google.genai import types

from aurora.conversa import TravasPorSessao, listar_pendencias
from aurora.conversa.eventos import serializar_eventos
from aurora.conversa.resposta import extrair_texto_final

CONFIRMACAO = "adk_request_confirmation"


def pedido(id_: str, tool: str = "reservar_area", args: dict | None = None) -> Event:
    chamada = types.FunctionCall(
        id=id_, name=CONFIRMACAO, args={"originalFunctionCall": {"id": "x", "name": tool, "args": args or {}}}
    )
    return Event(author="reservas", content=types.Content(role="model", parts=[types.Part(function_call=chamada)]))


def resposta(id_: str) -> Event:
    parte = types.Part(function_response=types.FunctionResponse(id=id_, name=CONFIRMACAO, response={"confirmed": True}))
    return Event(author="user", content=types.Content(role="user", parts=[parte]))


def fala(autor: str, conteudo: str, *, parcial: bool = False, raciocinio: bool = False) -> Event:
    parte = types.Part(text=conteudo, thought=raciocinio or None)
    return Event(author=autor, partial=parcial, content=types.Content(role="model", parts=[parte]))


def test_pendencias_ignora_respondidas_e_preserva_ordem() -> None:
    eventos = [pedido("a", args={"area": "quadra"}), pedido("b"), resposta("a"), pedido("c", "autorizar_visitante")]
    pendentes = listar_pendencias(eventos)
    assert [p.id for p in pendentes] == ["b", "c"]
    assert pendentes[1].nome_tool == "autorizar_visitante"


def test_pendencias_vazia_sem_pedidos_e_com_payload_malformado() -> None:
    assert listar_pendencias([fala("concierge", "oi")]) == []
    malformado = Event(
        author="reservas",
        content=types.Content(
            role="model", parts=[types.Part(function_call=types.FunctionCall(id="z", name=CONFIRMACAO))]
        ),
    )
    (pendente,) = listar_pendencias([malformado])
    assert pendente.nome_tool is None and dict(pendente.argumentos) == {}


def test_texto_final_ignora_usuario_parciais_e_raciocinio() -> None:
    eventos = [
        fala("user", "oi"),
        fala("reservas", "parcial", parcial=True),
        fala("reservas", "pensando", raciocinio=True),
        fala("reservas", "Primeira."),
        fala("reservas", "Segunda."),
    ]
    assert extrair_texto_final(eventos) == "Primeira.\n\nSegunda."
    assert extrair_texto_final([pedido("a")]) == ""


def test_serializar_eventos_mantem_ordem_e_conteudo() -> None:
    eventos = [fala("concierge", "um"), pedido("a")]
    saida = serializar_eventos(eventos)
    assert saida[0]["content"]["parts"][0]["text"] == "um"
    assert saida[1]["content"]["parts"][0]["functionCall"]["name"] == CONFIRMACAO


async def test_travas_serializam_mesma_sessao_e_liberam_sessoes_diferentes() -> None:
    travas = TravasPorSessao()
    assert travas.de("a") is travas.de("a") and travas.de("a") is not travas.de("b")
    ordem: list[str] = []

    async def usar(sessao: str, nome: str) -> None:
        async with travas.de(sessao):
            ordem.append(f"in:{nome}")
            await asyncio.sleep(0.05)
            ordem.append(f"out:{nome}")

    await asyncio.gather(usar("a", "1"), usar("a", "2"), usar("b", "3"))
    assert ordem.index("out:1") < ordem.index("in:2")  # mesma sessão: sem sobreposição
    assert ordem.index("in:3") < ordem.index("out:1")  # outra sessão: em paralelo
