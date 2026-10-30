"""Composition root: o único módulo que liga as implementações concretas de todas as features."""

import logging
from collections.abc import Mapping

from google.adk.models import BaseLlm
from google.adk.runners import Runner

from aurora.agentes import DescritorAcoesPadrao, criar_app_adk
from aurora.api.aplicacao import Aplicacao
from aurora.ciclo_de_vida import carregar_dados_iniciais, preparar_banco
from aurora.config import Configuracoes
from aurora.conversa import ServicoConversaAdk, criar_servico_sessao
from aurora.dominio import CatalogoAreas, ServicoReservasPadrao, ServicoVisitantesPadrao
from aurora.infra import criar_engine_sqlite
from aurora.persistencia import criar_repositorios
from aurora.regulamento import criar_ferramenta_regulamento

__all__ = ["montar_aplicacao"]

_LOG = logging.getLogger(__name__)


async def montar_aplicacao(configuracoes: Configuracoes, *, modelos: Mapping[str, BaseLlm] | None = None) -> Aplicacao:
    """Cria engines, repositórios, serviços, agentes e conversa; aplica o seed só se o banco não foi semeado.

    Args:
        modelos: Substituição de modelo por agente (só para testes com LLM roteirizado).

    Raises:
        ValueError: Configuração ou regulamento inválidos (a API não sobe).
    """
    engine = criar_engine_sqlite(configuracoes.banco_dominio, busy_timeout_ms=configuracoes.sqlite_busy_timeout_ms)
    repos = criar_repositorios(engine)
    if await preparar_banco(repos.carga, lambda: carregar_dados_iniciais(configuracoes.diretorio_dados)):
        _LOG.info("banco_semeado")

    areas = CatalogoAreas(await repos.referencia.listar_areas())
    servico_reservas = ServicoReservasPadrao(reservas=repos.reservas, areas=areas)
    servico_visitantes = ServicoVisitantesPadrao(visitantes=repos.visitantes)

    app_adk = criar_app_adk(
        configuracoes=configuracoes,
        servico_reservas=servico_reservas,
        servico_visitantes=servico_visitantes,
        ferramenta_regulamento=criar_ferramenta_regulamento(configuracoes=configuracoes),
        modelos=modelos,
    )
    servico_sessao = criar_servico_sessao(configuracoes)
    runner = Runner(app=app_adk, session_service=servico_sessao)
    conversa = ServicoConversaAdk(
        runner=runner,
        servico_sessao=servico_sessao,
        indice=repos.sessoes,
        catalogo=repos.referencia,
        descritor=DescritorAcoesPadrao(servico_reservas),
        nome_app=configuracoes.nome_app,
    )

    async def fechar() -> None:
        await runner.close()
        await servico_sessao.db_engine.dispose()
        await engine.dispose()

    return Aplicacao(conversa=conversa, reservas=servico_reservas, visitantes=servico_visitantes, fechar=fechar)
