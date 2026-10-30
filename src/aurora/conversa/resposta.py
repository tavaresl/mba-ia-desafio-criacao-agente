"""Texto final de uma invocação."""

from collections.abc import Iterable

from google.adk.events import Event

__all__ = ["extrair_texto_final"]


def extrair_texto_final(eventos_da_invocacao: Iterable[Event]) -> str:
    """Concatena o texto visível das respostas dos agentes (autor ≠ user, não parcial, sem raciocínio).

    Devolve `""` quando a execução parou sem texto (ex.: esperando confirmação).
    """
    trechos: list[str] = []
    for evento in eventos_da_invocacao:
        if evento.author == "user" or evento.partial or not evento.content or not evento.content.parts:
            continue
        trechos.extend(parte.text.strip() for parte in evento.content.parts if parte.text and not parte.thought)
    return "\n\n".join(t for t in trechos if t)
