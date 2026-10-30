"""Leitura e validação dos JSON de `dados/` (somente leitura, GR-08)."""

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from aurora.contratos import Apartamento, Area, DadosIniciais, Reserva, Visitante

__all__ = ["DadosIniciaisInvalidos", "carregar_dados_iniciais"]


class DadosIniciaisInvalidos(Exception):
    """Formato inesperado em `dados/`; a mensagem aponta o arquivo e o registro."""


def _ler(diretorio: Path, arquivo: str) -> list[dict[str, Any]]:
    try:
        conteudo = json.loads((diretorio / arquivo).read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise DadosIniciaisInvalidos(f"{arquivo}: arquivo não encontrado") from erro
    except json.JSONDecodeError as erro:
        raise DadosIniciaisInvalidos(f"{arquivo}: JSON malformado ({erro})") from erro
    if not isinstance(conteudo, list):
        raise DadosIniciaisInvalidos(f"{arquivo}: esperada uma lista de registros")
    return conteudo


def _converter[T](
    arquivo: str, registros: list[dict[str, Any]], construir: Callable[[dict[str, Any]], T]
) -> tuple[T, ...]:
    itens: list[T] = []
    for posicao, registro in enumerate(registros, start=1):
        try:
            itens.append(construir(registro))
        except (KeyError, TypeError, ValueError, InvalidOperation) as erro:
            raise DadosIniciaisInvalidos(f"{arquivo}: registro {posicao} inválido ({erro!r})") from erro
    return tuple(itens)


def carregar_dados_iniciais(diretorio: Path) -> DadosIniciais:
    """Lê os quatro JSON, converte para DTOs e valida a consistência entre eles.

    Raises:
        DadosIniciaisInvalidos: Arquivo ausente, malformado ou com referência inconsistente.
    """
    apartamentos = _converter(
        "apartamentos.json",
        _ler(diretorio, "apartamentos.json"),
        lambda r: Apartamento(str(r["numero"]), str(r["morador"])),
    )
    areas = _converter(
        "areas.json",
        _ler(diretorio, "areas.json"),
        lambda r: Area(str(r["id"]), str(r["nome"]), Decimal(str(r["taxa"]))),
    )
    reservas = _converter(
        "reservas.json",
        _ler(diretorio, "reservas.json"),
        lambda r: Reserva(str(r["codigo"]), str(r["apartamento"]), str(r["area"]), date.fromisoformat(r["data"])),
    )
    visitantes = _converter(
        "visitantes.json",
        _ler(diretorio, "visitantes.json"),
        lambda r: Visitante(str(r["apartamento"]), str(r["nome"]), date.fromisoformat(r["data"])),
    )
    _validar_consistencia(apartamentos, areas, reservas, visitantes)
    return DadosIniciais(apartamentos, areas, reservas, visitantes)


def _validar_consistencia(
    apartamentos: tuple[Apartamento, ...],
    areas: tuple[Area, ...],
    reservas: tuple[Reserva, ...],
    visitantes: tuple[Visitante, ...],
) -> None:
    numeros = {a.numero for a in apartamentos}
    ids_areas = {a.id for a in areas}
    vistos: set[tuple[str, date]] = set()
    codigos: set[str] = set()
    for reserva in reservas:
        if reserva.apartamento not in numeros:
            raise DadosIniciaisInvalidos(f"reservas.json: apartamento inexistente na reserva {reserva.codigo}")
        if reserva.area_id not in ids_areas:
            raise DadosIniciaisInvalidos(f"reservas.json: área inexistente na reserva {reserva.codigo}")
        if reserva.codigo in codigos:
            raise DadosIniciaisInvalidos(f"reservas.json: código repetido {reserva.codigo}")
        if (reserva.area_id, reserva.data) in vistos:
            raise DadosIniciaisInvalidos(f"reservas.json: duas reservas para a mesma área e data ({reserva.codigo})")
        codigos.add(reserva.codigo)
        vistos.add((reserva.area_id, reserva.data))
    for posicao, visitante in enumerate(visitantes, start=1):
        if visitante.apartamento not in numeros:
            raise DadosIniciaisInvalidos(f"visitantes.json: registro {posicao} com apartamento inexistente")
