"""Rotas de conversa: finas, só traduzem HTTP para `ServicoConversa`."""

from typing import Any

from fastapi import APIRouter, Request

from aurora.api.esquemas import (
    ConfirmacaoEntrada,
    ConfirmacaoPendenteSaida,
    CriarSessaoEntrada,
    CriarSessaoSaida,
    MensagemEntrada,
    RespostaConversaSaida,
)
from aurora.contratos import RespostaConversa, ServicoConversa

__all__ = ["roteador_sessoes"]

roteador_sessoes = APIRouter(prefix="/sessoes", tags=["sessões"])


def _conversa(request: Request) -> ServicoConversa:
    return request.app.state.aplicacao.conversa


def _saida(resposta: RespostaConversa) -> RespostaConversaSaida:
    return RespostaConversaSaida(
        resposta=resposta.resposta,
        confirmacoes_pendentes=[
            ConfirmacaoPendenteSaida(id=c.id, acao=c.acao, detalhes=dict(c.detalhes))
            for c in resposta.confirmacoes_pendentes
        ],
    )


@roteador_sessoes.post("", status_code=201, response_model=CriarSessaoSaida)
async def criar_sessao(corpo: CriarSessaoEntrada, request: Request) -> CriarSessaoSaida:
    return CriarSessaoSaida(session_id=await _conversa(request).criar_sessao(corpo.apartamento))


@roteador_sessoes.post("/{session_id}/mensagens", response_model=RespostaConversaSaida)
async def enviar_mensagem(session_id: str, corpo: MensagemEntrada, request: Request) -> RespostaConversaSaida:
    return _saida(await _conversa(request).enviar_mensagem(session_id, corpo.texto))


@roteador_sessoes.post("/{session_id}/confirmacoes", response_model=RespostaConversaSaida)
async def responder_confirmacao(session_id: str, corpo: ConfirmacaoEntrada, request: Request) -> RespostaConversaSaida:
    return _saida(await _conversa(request).responder_confirmacao(session_id, corpo.id, corpo.confirmado))


@roteador_sessoes.get("/{session_id}/eventos")
async def listar_eventos(session_id: str, request: Request) -> list[dict[str, Any]]:
    return await _conversa(request).listar_eventos(session_id)
