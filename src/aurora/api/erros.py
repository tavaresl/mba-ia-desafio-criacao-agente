"""Mapeamento exaustivo de exceções para status HTTP, com corpo genérico."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from aurora.contratos import (
    ApartamentoInvalido,
    ConfirmacaoNaoPendente,
    ModeloIndisponivel,
    SessaoNaoEncontrada,
)

__all__ = ["registrar_tratadores_de_erro"]

_LOG = logging.getLogger(__name__)


def _resposta(status: int, detalhe: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detalhe})


def registrar_tratadores_de_erro(app: FastAPI) -> None:
    @app.exception_handler(SessaoNaoEncontrada)
    async def _sessao(_: Request, __: SessaoNaoEncontrada) -> JSONResponse:
        return _resposta(404, "sessão não encontrada")

    @app.exception_handler(ConfirmacaoNaoPendente)
    async def _confirmacao(_: Request, __: ConfirmacaoNaoPendente) -> JSONResponse:
        return _resposta(409, "não existe confirmação pendente com esse id nesta sessão")

    @app.exception_handler(ApartamentoInvalido)
    async def _apartamento(_: Request, __: ApartamentoInvalido) -> JSONResponse:
        return _resposta(422, "apartamento inválido")

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, __: RequestValidationError) -> JSONResponse:
        return _resposta(422, "requisição inválida")

    @app.exception_handler(ModeloIndisponivel)
    async def _modelo(_: Request, __: ModeloIndisponivel) -> JSONResponse:
        return _resposta(503, "assistente indisponível no momento")

    @app.exception_handler(OperationalError)
    async def _banco(_: Request, erro: OperationalError) -> JSONResponse:
        _LOG.error("banco_indisponivel erro=%s", erro.orig)
        return _resposta(503, "serviço temporariamente indisponível")

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, erro: Exception) -> JSONResponse:
        _LOG.error("erro_inesperado", exc_info=erro)
        return _resposta(500, "erro interno")
