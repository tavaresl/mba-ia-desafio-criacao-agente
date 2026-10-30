"""Montagem de teste: App real, serviços de domínio reais, SQLite em disco e LLM roteirizado."""

import dataclasses
from pathlib import Path

from google.adk.runners import Runner
from google.adk.tools import FunctionTool

from aurora.agentes import DescritorAcoesPadrao, criar_app_adk
from aurora.ciclo_de_vida import carregar_dados_iniciais, preparar_banco
from aurora.config import Configuracoes, carregar_configuracoes
from aurora.conversa import ServicoConversaAdk, criar_servico_sessao
from aurora.dominio import CatalogoAreas, ServicoReservasPadrao, ServicoVisitantesPadrao
from aurora.infra import criar_engine_sqlite
from aurora.persistencia import criar_repositorios
from tests.fakes.llm_roteirizado import RoteiroLlm

RAIZ = Path(__file__).resolve().parents[2]


async def regulamento(request: str) -> str:
    """Responde dúvidas sobre o regulamento (stub)."""
    return "stub"


class Montagem:
    """Equivale à montagem de produção; `reiniciar()` recria tudo sobre os mesmos arquivos."""

    def __init__(self, tmp_path: Path, llms: dict[str, RoteiroLlm]) -> None:
        base = carregar_configuracoes(RAIZ, exigir_chave=False)
        self.config: Configuracoes = dataclasses.replace(
            base, banco_dominio=tmp_path / "aurora.db", banco_sessoes=tmp_path / "sessions.db"
        )
        self.llms = llms

    async def iniciar(self) -> "Montagem":
        self.engine = criar_engine_sqlite(self.config.banco_dominio, busy_timeout_ms=self.config.sqlite_busy_timeout_ms)
        self.repos = criar_repositorios(self.engine)
        await preparar_banco(self.repos.carga, lambda: carregar_dados_iniciais(self.config.diretorio_dados))
        areas = CatalogoAreas(await self.repos.referencia.listar_areas())
        self.reservas = ServicoReservasPadrao(reservas=self.repos.reservas, areas=areas)
        self.visitantes = ServicoVisitantesPadrao(visitantes=self.repos.visitantes)
        app = criar_app_adk(
            configuracoes=self.config,
            servico_reservas=self.reservas,
            servico_visitantes=self.visitantes,
            ferramenta_regulamento=FunctionTool(regulamento),
            modelos=self.llms,
        )
        self.servico_sessao = criar_servico_sessao(self.config)
        self.runner = Runner(app=app, session_service=self.servico_sessao)
        self.conversa = ServicoConversaAdk(
            runner=self.runner,
            servico_sessao=self.servico_sessao,
            indice=self.repos.sessoes,
            catalogo=self.repos.referencia,
            descritor=DescritorAcoesPadrao(self.reservas),
            nome_app=self.config.nome_app,
        )
        return self

    async def encerrar(self) -> None:
        await self.servico_sessao.db_engine.dispose()
        await self.engine.dispose()

    async def reiniciar(self) -> "Montagem":
        """Simula Ctrl+C e nova subida sem restaurar os dados."""
        await self.encerrar()
        return await self.iniciar()
