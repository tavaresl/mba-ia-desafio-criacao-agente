"""Ponto de entrada de `uv run aurora-restaurar`."""

import asyncio
import sys

from sqlalchemy.exc import OperationalError

from aurora.ciclo_de_vida.dados_iniciais import DadosIniciaisInvalidos, carregar_dados_iniciais
from aurora.ciclo_de_vida.restauracao import ResumoRestauracao, restaurar
from aurora.config import Configuracoes, carregar_configuracoes
from aurora.infra import configurar_logs, criar_engine_sqlite
from aurora.persistencia import criar_repositorios

__all__ = ["main"]

SAIDA_OK = 0
SAIDA_DADOS_INVALIDOS = 1
SAIDA_BANCO_TRAVADO = 2


async def _executar(configuracoes: Configuracoes) -> ResumoRestauracao:
    dados = carregar_dados_iniciais(configuracoes.diretorio_dados)  # falha antes de alterar qualquer coisa
    engine = criar_engine_sqlite(configuracoes.banco_dominio, busy_timeout_ms=configuracoes.sqlite_busy_timeout_ms)
    try:
        repos = criar_repositorios(engine)
        return await restaurar(
            carga=repos.carga,
            indice_sessoes=repos.sessoes,
            banco_sessoes=configuracoes.banco_sessoes,
            dados=dados,
        )
    finally:
        await engine.dispose()


def main() -> None:
    """Restaura reservas e visitantes ao estado de `dados/` e apaga as sessões. Pare a API antes."""
    configurar_logs("WARNING")
    configuracoes = carregar_configuracoes(exigir_chave=False)
    try:
        resumo = asyncio.run(_executar(configuracoes))
    except DadosIniciaisInvalidos as erro:
        print(f"Dados iniciais inválidos: {erro}", file=sys.stderr)
        sys.exit(SAIDA_DADOS_INVALIDOS)
    except OperationalError as erro:
        print(f"Banco travado ({erro.orig}). Pare a API antes de restaurar.", file=sys.stderr)
        sys.exit(SAIDA_BANCO_TRAVADO)
    print(
        f"Restauração concluída: {resumo.reservas} reservas, {resumo.visitantes} visitantes; "
        f"sessões {'apagadas' if resumo.sessoes_apagadas else 'mantidas'}."
    )
