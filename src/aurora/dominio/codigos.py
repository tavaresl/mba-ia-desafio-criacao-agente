"""Geração de códigos de reserva (ADR-014)."""

import secrets

__all__ = ["ALFABETO_CODIGO", "TAMANHO_CODIGO", "gerar_codigo_reserva"]

ALFABETO_CODIGO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TAMANHO_CODIGO = 6


def gerar_codigo_reserva() -> str:
    """Gera `RSV-` + 6 caracteres Crockford base32 (ex.: `RSV-7K2Q9M`).

    O formato difere dos códigos iniciais (`RSV-NNNN`); a unicidade definitiva é garantida pelo repositório.
    """
    return "RSV-" + "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(TAMANHO_CODIGO))
