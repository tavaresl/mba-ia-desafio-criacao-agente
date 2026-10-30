"""Ponto de entrada de `uv run aurora-api`."""

import sys

import uvicorn

from aurora.api.app import criar_app_http
from aurora.api.montagem import montar_aplicacao
from aurora.config import carregar_configuracoes
from aurora.infra import configurar_logs

__all__ = ["main"]


def main() -> None:
    """Sobe a API em `http://localhost:8000` (processo único: os locks por sessão dependem disso)."""
    configurar_logs()
    try:
        configuracoes = carregar_configuracoes()
    except ValueError as erro:
        print(f"Configuração inválida: {erro}", file=sys.stderr)
        sys.exit(1)
    app = criar_app_http(lambda: montar_aplicacao(configuracoes))
    uvicorn.run(app, host=configuracoes.host, port=configuracoes.porta, workers=1, log_config=None)
