"""Aplicação FastAPI: rotas, tratadores de erro, log de acesso e `lifespan`."""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from aurora.api.aplicacao import Aplicacao
from aurora.api.erros import registrar_tratadores_de_erro
from aurora.api.rotas_sessoes import roteador_sessoes
from aurora.api.rotas_verificacao import roteador_verificacao

__all__ = ["criar_app_http"]

_LOG = logging.getLogger("aurora.acesso")


def criar_app_http(montar: Callable[[], Awaitable[Aplicacao]]) -> FastAPI:
    """Cria o app HTTP. A montagem roda no `lifespan` (objetos caros criados uma vez) e é fechada no shutdown."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.aplicacao = await montar()
        try:
            yield
        finally:
            await app.state.aplicacao.fechar()

    app = FastAPI(title="Assistente do Residencial Aurora", lifespan=lifespan)
    registrar_tratadores_de_erro(app)
    app.include_router(roteador_sessoes)
    app.include_router(roteador_verificacao)

    @app.middleware("http")
    async def registrar_acesso(request: Request, chamar: Callable[[Request], Awaitable[Response]]) -> Response:
        inicio = time.perf_counter()
        resposta = await chamar(request)
        _LOG.info(
            "metodo=%s rota=%s status=%d duracao_ms=%d",
            request.method,
            request.url.path,
            resposta.status_code,
            (time.perf_counter() - inicio) * 1000,
        )
        return resposta

    return app
