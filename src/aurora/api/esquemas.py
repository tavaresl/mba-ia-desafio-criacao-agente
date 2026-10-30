"""Esquemas Pydantic fiéis ao contrato do enunciado."""

from typing import Any

from pydantic import BaseModel

__all__ = [
    "ConfirmacaoEntrada",
    "ConfirmacaoPendenteSaida",
    "CriarSessaoEntrada",
    "CriarSessaoSaida",
    "MensagemEntrada",
    "RespostaConversaSaida",
    "ReservaSaida",
    "VisitanteSaida",
]


class CriarSessaoEntrada(BaseModel):
    apartamento: str


class CriarSessaoSaida(BaseModel):
    session_id: str


class MensagemEntrada(BaseModel):
    texto: str


class ConfirmacaoEntrada(BaseModel):
    id: str
    confirmado: bool


class ConfirmacaoPendenteSaida(BaseModel):
    id: str
    acao: str
    detalhes: dict[str, Any]


class RespostaConversaSaida(BaseModel):
    resposta: str
    confirmacoes_pendentes: list[ConfirmacaoPendenteSaida]


class ReservaSaida(BaseModel):
    codigo: str
    area: str
    data: str


class VisitanteSaida(BaseModel):
    nome: str
    data: str
