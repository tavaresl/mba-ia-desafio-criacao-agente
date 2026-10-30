"""Conversão dos resultados de domínio para a saída mínima das tools (ADR-010).

Os campos devolvidos aqui são a lista exaustiva do que pode chegar ao modelo e aos eventos da sessão.
"""

from typing import Any

from aurora.contratos import (
    Area,
    Disponibilidade,
    EntradaInvalida,
    Indisponivel,
    NaoEncontrada,
    Reserva,
    ReservaCancelada,
    ReservaCriada,
    Visitante,
    VisitanteAutorizado,
)

__all__ = ["serializar", "serializar_areas", "serializar_reservas", "serializar_visitantes"]


def serializar(resultado: object) -> dict[str, Any]:
    """Converte um `Resultado*` do domínio num `dict` mínimo; tipo desconhecido falha (nunca vaza)."""
    match resultado:
        case ReservaCriada(codigo=codigo, area_id=area, data=data):
            return {"status": "reservada", "codigo": codigo, "area": area, "data": data.isoformat()}
        case ReservaCancelada(codigo=codigo, area_id=area, data=data):
            return {"status": "cancelada", "codigo": codigo, "area": area, "data": data.isoformat()}
        case Indisponivel(area_id=area, data=data):
            return {"status": "indisponivel", "area": area, "data": data.isoformat()}
        case NaoEncontrada():
            return {"status": "nao_encontrada"}
        case Disponibilidade(area_id=area, data=data, disponivel=disponivel):
            return {"area": area, "data": data.isoformat(), "disponivel": disponivel}
        case VisitanteAutorizado(nome=nome, data=data):
            return {"status": "autorizado", "nome": nome, "data": data.isoformat()}
        case EntradaInvalida(motivo=motivo):
            return {"status": "entrada_invalida", "motivo": str(motivo)}
        case _:
            raise TypeError(f"resultado sem serialização definida: {type(resultado).__name__}")


def serializar_reservas(reservas: list[Reserva]) -> dict[str, Any]:
    return {"reservas": [{"codigo": r.codigo, "area": r.area_id, "data": r.data.isoformat()} for r in reservas]}


def serializar_visitantes(visitantes: list[Visitante]) -> dict[str, Any]:
    return {"visitantes": [{"nome": v.nome, "data": v.data.isoformat()} for v in visitantes]}


def serializar_areas(areas: list[Area]) -> dict[str, Any]:
    return {"areas": [{"id": a.id, "nome": a.nome, "taxa": f"{a.taxa:.2f}"} for a in areas]}
