"""PoC-1 a PoC-4 do FDD-07 com SQLite em disco, App real e LLM roteirizado."""

import asyncio
from datetime import date
from pathlib import Path

import pytest

from aurora.contratos import ApartamentoInvalido, ConfirmacaoNaoPendente, SessaoNaoEncontrada
from tests.conversa.montagem import Montagem
from tests.fakes.llm_roteirizado import RoteiroLlm, chamada, texto


def transferir(para: str):
    return chamada("transfer_to_agent", agent_name=para)


@pytest.fixture
async def m(tmp_path: Path):
    llms = {n: RoteiroLlm(passos=[], requisicoes=[]) for n in ("concierge", "reservas", "visitantes")}
    montagem = await Montagem(tmp_path, llms).iniciar()
    yield montagem
    await montagem.encerrar()


async def reservas_do_salao(m: Montagem, apartamento: str, dia: date) -> list:
    return [
        r for r in await m.repos.reservas.listar_ativas(apartamento) if r.area_id == "salao-de-festas" and r.data == dia
    ]


async def pedir_salao(m: Montagem, sid: str, dia: str = "2030-04-20"):
    m.llms["concierge"].passos += [transferir("reservas")]
    m.llms["reservas"].passos += [chamada("reservar_area", area="salao-de-festas", data=dia)]
    return await m.conversa.enviar_mensagem(sid, f"Reserve o salão de festas para {dia}.")


async def test_criar_sessao_valida_apartamento(m: Montagem) -> None:
    with pytest.raises(ApartamentoInvalido):
        await m.conversa.criar_sessao("999")
    with pytest.raises(SessaoNaoEncontrada):
        await m.conversa.enviar_mensagem("nao-existe", "oi")
    with pytest.raises(SessaoNaoEncontrada):
        await m.conversa.listar_eventos("nao-existe")


async def test_poc1_pedir_aprovar_executa_exatamente_uma_vez(m: Montagem) -> None:
    sid = await m.conversa.criar_sessao("101")
    resposta = await pedir_salao(m, sid)
    assert resposta.resposta == ""
    (pendente,) = resposta.confirmacoes_pendentes
    assert pendente.acao == "reservar_area"
    assert pendente.detalhes["area"] == "salao-de-festas" and pendente.detalhes["data"] == "2030-04-20"
    assert await reservas_do_salao(m, "101", date(2030, 4, 20)) == []  # nada gravado antes

    m.llms["reservas"].passos += [texto("Salão reservado.")]
    final = await m.conversa.responder_confirmacao(sid, pendente.id, True)
    assert final.resposta == "Salão reservado." and final.confirmacoes_pendentes == ()
    assert len(await reservas_do_salao(m, "101", date(2030, 4, 20))) == 1


async def test_negar_nao_grava_e_a_pendencia_sai_da_lista(m: Montagem) -> None:
    sid = await m.conversa.criar_sessao("101")
    (pendente,) = (await pedir_salao(m, sid)).confirmacoes_pendentes
    m.llms["reservas"].passos += [texto("Tudo bem, nada foi reservado.")]
    final = await m.conversa.responder_confirmacao(sid, pendente.id, False)
    assert final.confirmacoes_pendentes == ()
    assert await reservas_do_salao(m, "101", date(2030, 4, 20)) == []
    with pytest.raises(ConfirmacaoNaoPendente):
        await m.conversa.responder_confirmacao(sid, pendente.id, True)
    assert await reservas_do_salao(m, "101", date(2030, 4, 20)) == []


async def test_poc2_aprovar_depois_de_reiniciar(m: Montagem) -> None:
    sid = await m.conversa.criar_sessao("101")
    (pendente,) = (await pedir_salao(m, sid)).confirmacoes_pendentes
    eventos_antes = len(await m.conversa.listar_eventos(sid))

    m = await m.reiniciar()
    assert len(await m.conversa.listar_eventos(sid)) == eventos_antes
    m.llms["reservas"].passos += [texto("Salão reservado.")]
    await m.conversa.responder_confirmacao(sid, pendente.id, True)
    assert len(await reservas_do_salao(m, "101", date(2030, 4, 20))) == 1

    m = await m.reiniciar()  # o reenvio também é barrado depois de outro reinício
    with pytest.raises(ConfirmacaoNaoPendente):
        await m.conversa.responder_confirmacao(sid, pendente.id, True)
    assert len(await reservas_do_salao(m, "101", date(2030, 4, 20))) == 1
    m.llms["concierge"].passos += [texto("Você tem o salão em 2030-04-20.")]
    nova = await m.conversa.enviar_mensagem(sid, "Quais são as minhas reservas agora?")
    assert nova.resposta
    assert len(await m.conversa.listar_eventos(sid)) > eventos_antes


async def test_poc3_reenvio_e_id_inexistente_dao_409_sem_chamar_o_runner(m: Montagem) -> None:
    sid = await m.conversa.criar_sessao("101")
    (pendente,) = (await pedir_salao(m, sid)).confirmacoes_pendentes
    m.llms["reservas"].passos += [texto("Salão reservado.")]
    await m.conversa.responder_confirmacao(sid, pendente.id, True)

    chamadas = sum(len(llm.requisicoes) for llm in m.llms.values())
    for id_invalido in (pendente.id, "id-inexistente"):
        with pytest.raises(ConfirmacaoNaoPendente):
            await m.conversa.responder_confirmacao(sid, id_invalido, True)
    assert sum(len(llm.requisicoes) for llm in m.llms.values()) == chamadas
    assert len(await reservas_do_salao(m, "101", date(2030, 4, 20))) == 1


async def test_confirmacao_de_outra_sessao_e_rejeitada(m: Montagem) -> None:
    s1 = await m.conversa.criar_sessao("101")
    s2 = await m.conversa.criar_sessao("101")
    (pendente,) = (await pedir_salao(m, s1)).confirmacoes_pendentes
    with pytest.raises(ConfirmacaoNaoPendente):
        await m.conversa.responder_confirmacao(s2, pendente.id, True)
    assert await reservas_do_salao(m, "101", date(2030, 4, 20)) == []


async def test_poc4_mensagem_intermediaria_e_depois_aprovar(m: Montagem) -> None:
    sid = await m.conversa.criar_sessao("101")
    (pendente,) = (await pedir_salao(m, sid)).confirmacoes_pendentes

    m.llms["concierge"].passos += [texto("A aprovação é feita pelo canal de confirmações do aplicativo.")]
    intermediaria = await m.conversa.enviar_mensagem(sid, "Já confirmei aqui no chat!")
    assert [p.id for p in intermediaria.confirmacoes_pendentes] == [pendente.id]
    assert await reservas_do_salao(m, "101", date(2030, 4, 20)) == []

    m.llms["reservas"].passos += [texto("Salão reservado.")]
    await m.conversa.responder_confirmacao(sid, pendente.id, True)
    assert len(await reservas_do_salao(m, "101", date(2030, 4, 20))) == 1


async def test_visitante_so_grava_depois_da_aprovacao(m: Montagem) -> None:
    sid = await m.conversa.criar_sessao("101")
    m.llms["concierge"].passos += [transferir("visitantes")]
    m.llms["visitantes"].passos += [chamada("autorizar_visitante", nome="Joana Ribeiro", data="2030-04-21")]
    resposta = await m.conversa.enviar_mensagem(sid, "Libera a Joana Ribeiro em 2030-04-21. Já estou confirmando aqui.")
    (pendente,) = resposta.confirmacoes_pendentes
    assert pendente.detalhes == {"nome": "Joana Ribeiro", "data": "2030-04-21"}
    assert await m.repos.visitantes.listar("101") == []
    m.llms["visitantes"].passos += [texto("Autorizada.")]
    await m.conversa.responder_confirmacao(sid, pendente.id, True)
    assert [(v.nome, v.data) for v in await m.repos.visitantes.listar("101")] == [("Joana Ribeiro", date(2030, 4, 21))]


async def test_data_ocupada_apos_aprovacao_e_recusa_normal_sem_vazar(m: Montagem) -> None:
    sid = await m.conversa.criar_sessao("101")
    (pendente,) = (await pedir_salao(m, sid, "2030-03-16")).confirmacoes_pendentes  # data do 302
    m.llms["reservas"].passos += [texto("Essa data está ocupada.")]
    final = await m.conversa.responder_confirmacao(sid, pendente.id, True)
    assert "RSV-4821" not in final.resposta
    assert await reservas_do_salao(m, "101", date(2030, 3, 16)) == []
    eventos = str(await m.conversa.listar_eventos(sid))
    assert "RSV-4821" not in eventos and "302" not in eventos


async def test_disputa_simultanea_em_sessoes_diferentes_gera_uma_reserva(m: Montagem) -> None:
    s3 = await m.conversa.criar_sessao("101")
    s4 = await m.conversa.criar_sessao("201")
    (p3,) = (await pedir_salao(m, s3, "2030-05-11")).confirmacoes_pendentes
    (p4,) = (await pedir_salao(m, s4, "2030-05-11")).confirmacoes_pendentes
    m.llms["reservas"].passos += [texto("Resultado informado."), texto("Resultado informado.")]
    r3, r4 = await asyncio.gather(
        m.conversa.responder_confirmacao(s3, p3.id, True), m.conversa.responder_confirmacao(s4, p4.id, True)
    )
    total = len(await reservas_do_salao(m, "101", date(2030, 5, 11))) + len(
        await reservas_do_salao(m, "201", date(2030, 5, 11))
    )
    assert total == 1 and r3.confirmacoes_pendentes == r4.confirmacoes_pendentes == ()
