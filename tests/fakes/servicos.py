"""Fakes dos serviços de domínio e da conversa, para os testes de agentes e de API."""

from collections.abc import Mapping
from typing import Any

from aurora.contratos import (
    Area,
    ConfirmacaoNaoPendente,
    ConfirmacaoPendente,
    Reserva,
    RespostaConversa,
    SessaoNaoEncontrada,
    Visitante,
)


class ServicoConversaFalso:
    """Conversa roteirizada: toda mensagem gera uma pendência; sessões vivem em memória."""

    def __init__(self) -> None:
        self.sessoes: dict[str, list[str]] = {}
        self.pendencias: dict[str, dict[str, ConfirmacaoPendente]] = {}
        self._seq = 0

    async def criar_sessao(self, apartamento: str) -> str:
        self._seq += 1
        sid = f"sessao-{self._seq}"
        self.sessoes[sid] = []
        self.pendencias[sid] = {}
        return sid

    def _existe(self, session_id: str) -> None:
        if session_id not in self.sessoes:
            raise SessaoNaoEncontrada

    async def enviar_mensagem(self, session_id: str, texto: str) -> RespostaConversa:
        self._existe(session_id)
        self.sessoes[session_id].append(texto)
        pendencia = ConfirmacaoPendente(
            f"c{len(self.sessoes[session_id])}", "reservar_area", {"area": "x", "data": "y"}
        )
        self.pendencias[session_id][pendencia.id] = pendencia
        return RespostaConversa("", tuple(self.pendencias[session_id].values()))

    async def responder_confirmacao(self, session_id: str, confirmacao_id: str, confirmado: bool) -> RespostaConversa:
        self._existe(session_id)
        if self.pendencias[session_id].pop(confirmacao_id, None) is None:
            raise ConfirmacaoNaoPendente
        return RespostaConversa("ok" if confirmado else "negado", tuple(self.pendencias[session_id].values()))

    async def listar_eventos(self, session_id: str) -> list[dict[str, Any]]:
        self._existe(session_id)
        return [{"texto": t} for t in self.sessoes[session_id]]


class ServicoReservasFalso:
    def __init__(self, reservas: list[Reserva] | None = None) -> None:
        self.reservas = reservas or []

    def listar_areas(self) -> list[Area]:
        return []

    def resolver_area(self, area: str) -> Area | None:
        return None

    def exige_confirmacao(self, area: str) -> bool:
        return True

    async def listar_do_apartamento(self, apartamento: str) -> list[Reserva]:
        return [r for r in self.reservas if r.apartamento == apartamento]


class ServicoVisitantesFalso:
    def __init__(self, visitantes: list[Visitante] | None = None) -> None:
        self.visitantes = visitantes or []

    async def listar_do_apartamento(self, apartamento: str) -> list[Visitante]:
        return [v for v in self.visitantes if v.apartamento == apartamento]


class DescritorAcoesFalso:
    def descrever(self, nome_tool: str, argumentos: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        return nome_tool, dict(argumentos)
