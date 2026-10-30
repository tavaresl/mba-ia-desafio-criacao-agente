"""Validação e normalização das entradas vindas do modelo."""

import re
from datetime import date

__all__ = ["TAMANHO_MAXIMO_NOME_VISITANTE", "interpretar_data", "normalizar_nome_visitante"]

TAMANHO_MAXIMO_NOME_VISITANTE = 100
_PADRAO_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def interpretar_data(texto: str | None) -> date | None:
    """Interpreta `AAAA-MM-DD` estrito; devolve `None` para qualquer outro formato ou data inexistente."""
    if not texto or not _PADRAO_DATA.match(texto.strip()):
        return None
    try:
        return date.fromisoformat(texto.strip())
    except ValueError:
        return None


def normalizar_nome_visitante(texto: str | None) -> str | None:
    """Remove espaços nas pontas; rejeita vazio, longo demais ou com caracteres de controle."""
    if texto is None:
        return None
    nome = " ".join(texto.split())
    if not nome or len(nome) > TAMANHO_MAXIMO_NOME_VISITANTE or not nome.isprintable():
        return None
    return nome
