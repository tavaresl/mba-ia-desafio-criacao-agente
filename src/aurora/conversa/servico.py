"""Serviço de conversa: sessões persistentes, mensagens e retomada por confirmação (G1, G3)."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService, Session
from google.genai import errors as erros_genai
from google.genai import types

from aurora.contratos import (
    ApartamentoInvalido,
    CatalogoReferencia,
    ConfirmacaoNaoPendente,
    ConfirmacaoPendente,
    DescritorAcoes,
    IndiceSessoes,
    ModeloIndisponivel,
    RespostaConversa,
    SessaoNaoEncontrada,
)
from aurora.conversa.eventos import serializar_eventos
from aurora.conversa.pendencias import NOME_CHAMADA_CONFIRMACAO, listar_pendencias
from aurora.conversa.resposta import extrair_texto_final
from aurora.conversa.travas import TravasPorSessao

__all__ = ["ServicoConversaAdk"]

_LOG = logging.getLogger(__name__)


class ServicoConversaAdk:
    """Implementa `aurora.contratos.ServicoConversa` sobre o `Runner` do ADK."""

    def __init__(
        self,
        *,
        runner: Runner,
        servico_sessao: BaseSessionService,
        indice: IndiceSessoes,
        catalogo: CatalogoReferencia,
        descritor: DescritorAcoes,
        nome_app: str,
    ) -> None:
        self._runner = runner
        self._servico_sessao = servico_sessao
        self._indice = indice
        self._catalogo = catalogo
        self._descritor = descritor
        self._nome_app = nome_app
        self._travas = TravasPorSessao()

    async def criar_sessao(self, apartamento: str) -> str:
        """Cria a sessão com `user_id` = apartamento, definido uma única vez (G2, ADR-009)."""
        if not await self._catalogo.apartamento_existe(apartamento):
            raise ApartamentoInvalido
        sessao = await self._servico_sessao.create_session(app_name=self._nome_app, user_id=apartamento)
        try:
            await self._indice.registrar(session_id=sessao.id, apartamento=apartamento)
        except Exception:
            await self._servico_sessao.delete_session(
                app_name=self._nome_app, user_id=apartamento, session_id=sessao.id
            )
            raise
        _LOG.info("sessao_criada session_id=%s", sessao.id)
        return sessao.id

    async def enviar_mensagem(self, session_id: str, texto: str) -> RespostaConversa:
        async with self._travas.de(session_id):
            apartamento, _ = await self._resolver(session_id)
            conteudo = types.Content(role="user", parts=[types.Part(text=texto)])
            eventos = await self._executar(apartamento, session_id, conteudo)
            resposta = await self._compor(apartamento, session_id, eventos)
        _LOG.info(
            "mensagem_processada session_id=%s eventos=%d pendencias=%d",
            session_id,
            len(eventos),
            len(resposta.confirmacoes_pendentes),
        )
        return resposta

    async def responder_confirmacao(self, session_id: str, confirmacao_id: str, confirmado: bool) -> RespostaConversa:
        """Retoma a execução com o `FunctionResponse` do morador; `id` não pendente nunca chega ao `Runner`."""
        async with self._travas.de(session_id):
            apartamento, sessao = await self._resolver(session_id)
            if confirmacao_id not in {p.id for p in listar_pendencias(sessao.events)}:
                _LOG.warning("confirmacao_nao_pendente session_id=%s id=%s", session_id, confirmacao_id)
                raise ConfirmacaoNaoPendente
            parte = types.Part(
                function_response=types.FunctionResponse(
                    id=confirmacao_id, name=NOME_CHAMADA_CONFIRMACAO, response={"confirmed": confirmado}
                )
            )
            eventos = await self._executar(apartamento, session_id, types.Content(role="user", parts=[parte]))
            resposta = await self._compor(apartamento, session_id, eventos)
        _LOG.info("confirmacao_respondida session_id=%s id=%s confirmado=%s", session_id, confirmacao_id, confirmado)
        return resposta

    async def listar_eventos(self, session_id: str) -> list[dict[str, Any]]:
        _, sessao = await self._resolver(session_id)
        return serializar_eventos(sessao.events)

    async def _resolver(self, session_id: str) -> tuple[str, Session]:
        apartamento = await self._indice.apartamento_de(session_id)
        if apartamento is None:
            raise SessaoNaoEncontrada
        sessao = await self._servico_sessao.get_session(
            app_name=self._nome_app, user_id=apartamento, session_id=session_id
        )
        if sessao is None:
            raise SessaoNaoEncontrada
        return apartamento, sessao

    async def _executar(self, apartamento: str, session_id: str, conteudo: types.Content) -> list[Event]:
        try:
            return [
                evento
                async for evento in self._rodar(apartamento=apartamento, session_id=session_id, conteudo=conteudo)
            ]
        except erros_genai.APIError as erro:
            _LOG.error("modelo_indisponivel session_id=%s codigo=%s", session_id, erro.code)
            raise ModeloIndisponivel from erro

    def _rodar(self, *, apartamento: str, session_id: str, conteudo: types.Content) -> AsyncIterator[Event]:
        return self._runner.run_async(user_id=apartamento, session_id=session_id, new_message=conteudo)

    async def _compor(self, apartamento: str, session_id: str, eventos: list[Event]) -> RespostaConversa:
        sessao = await self._servico_sessao.get_session(
            app_name=self._nome_app, user_id=apartamento, session_id=session_id
        )
        pendentes = listar_pendencias(sessao.events) if sessao else []
        confirmacoes = tuple(
            ConfirmacaoPendente(p.id, *self._descritor.descrever(p.nome_tool or "", p.argumentos)) for p in pendentes
        )
        return RespostaConversa(resposta=extrair_texto_final(eventos), confirmacoes_pendentes=confirmacoes)
