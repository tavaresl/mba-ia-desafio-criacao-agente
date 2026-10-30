"""Contratos da camada de conversa (implementados em `aurora.conversa`)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

__all__ = [
    "ACAO_AUTORIZAR_VISITANTE",
    "ACAO_RESERVAR_AREA",
    "ApartamentoInvalido",
    "ConfirmacaoNaoPendente",
    "ConfirmacaoPendente",
    "DescritorAcoes",
    "ErroAplicacao",
    "ModeloIndisponivel",
    "RespostaConversa",
    "ServicoConversa",
    "SessaoNaoEncontrada",
]

ACAO_RESERVAR_AREA = "reservar_area"
ACAO_AUTORIZAR_VISITANTE = "autorizar_visitante"


@dataclass(frozen=True, slots=True)
class ConfirmacaoPendente:
    id: str
    acao: str
    detalhes: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class RespostaConversa:
    resposta: str
    confirmacoes_pendentes: tuple[ConfirmacaoPendente, ...]


class ErroAplicacao(Exception):
    """Base dos erros de aplicação mapeados para status HTTP."""


class SessaoNaoEncontrada(ErroAplicacao):
    pass


class ConfirmacaoNaoPendente(ErroAplicacao):
    pass


class ApartamentoInvalido(ErroAplicacao):
    pass


class ModeloIndisponivel(ErroAplicacao):
    pass


class DescritorAcoes(Protocol):
    def descrever(self, nome_tool: str, argumentos: Mapping[str, Any]) -> tuple[str, dict[str, Any]]: ...


class ServicoConversa(Protocol):
    async def criar_sessao(self, apartamento: str) -> str: ...

    async def enviar_mensagem(self, session_id: str, texto: str) -> RespostaConversa: ...

    async def responder_confirmacao(
        self, session_id: str, confirmacao_id: str, confirmado: bool
    ) -> RespostaConversa: ...

    async def listar_eventos(self, session_id: str) -> list[dict[str, Any]]: ...
