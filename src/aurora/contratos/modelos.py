"""DTOs imutáveis e tipos de resultado do domínio (ADR-010)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

__all__ = [
    "Apartamento",
    "Area",
    "DadosIniciais",
    "Disponibilidade",
    "EntradaInvalida",
    "Indisponivel",
    "MotivoInvalido",
    "NaoEncontrada",
    "Reserva",
    "ReservaCancelada",
    "ReservaCriada",
    "ResultadoCancelamento",
    "ResultadoConsulta",
    "ResultadoReserva",
    "ResultadoVisitante",
    "Visitante",
    "VisitanteAutorizado",
]


@dataclass(frozen=True, slots=True)
class Area:
    id: str
    nome: str
    taxa: Decimal


@dataclass(frozen=True, slots=True)
class Apartamento:
    numero: str
    morador: str


@dataclass(frozen=True, slots=True)
class Reserva:
    codigo: str
    apartamento: str
    area_id: str
    data: date


@dataclass(frozen=True, slots=True)
class Visitante:
    apartamento: str
    nome: str
    data: date


class MotivoInvalido(StrEnum):
    AREA_INEXISTENTE = "area_inexistente"
    DATA_INVALIDA = "data_invalida"
    NOME_INVALIDO = "nome_invalido"
    IDENTIFICACAO_INCOMPLETA = "identificacao_incompleta"


@dataclass(frozen=True, slots=True)
class EntradaInvalida:
    motivo: MotivoInvalido


@dataclass(frozen=True, slots=True)
class Disponibilidade:
    area_id: str
    data: date
    disponivel: bool


@dataclass(frozen=True, slots=True)
class ReservaCriada:
    codigo: str
    area_id: str
    data: date


@dataclass(frozen=True, slots=True)
class ReservaCancelada:
    codigo: str
    area_id: str
    data: date


@dataclass(frozen=True, slots=True)
class Indisponivel:
    """Data ocupada. Nunca contém dono nem código da reserva existente."""

    area_id: str
    data: date


@dataclass(frozen=True, slots=True)
class NaoEncontrada:
    """Indistinguível: reserva inexistente ou pertencente a terceiro."""


@dataclass(frozen=True, slots=True)
class VisitanteAutorizado:
    nome: str
    data: date


ResultadoConsulta = Disponibilidade | EntradaInvalida
ResultadoReserva = ReservaCriada | Indisponivel | EntradaInvalida
ResultadoCancelamento = ReservaCancelada | NaoEncontrada | EntradaInvalida
ResultadoVisitante = VisitanteAutorizado | EntradaInvalida


@dataclass(frozen=True, slots=True)
class DadosIniciais:
    apartamentos: tuple[Apartamento, ...]
    areas: tuple[Area, ...]
    reservas: tuple[Reserva, ...]
    visitantes: tuple[Visitante, ...]
