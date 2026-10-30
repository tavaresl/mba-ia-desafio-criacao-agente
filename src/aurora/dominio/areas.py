"""Catálogo de áreas: normalização de nomes e política de confirmação (RN-02)."""

import re
import unicodedata
from collections.abc import Sequence

from aurora.contratos import Area

__all__ = ["CatalogoAreas"]


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[\s\-_]+", " ", sem_acento.lower()).strip()


class CatalogoAreas:
    """Dado de referência imutável, carregado uma vez na montagem."""

    def __init__(self, areas: Sequence[Area]) -> None:
        self._areas = tuple(areas)
        self._indice: dict[str, Area] = {}
        for area in self._areas:
            self._indice[_normalizar(area.id)] = area
            self._indice[_normalizar(area.nome)] = area

    def listar(self) -> list[Area]:
        return list(self._areas)

    def resolver(self, texto: str) -> Area | None:
        """Aceita só correspondência exata (após normalização) com o `id` ou o `nome`."""
        return self._indice.get(_normalizar(texto))

    def exige_confirmacao(self, texto: str) -> bool:
        """Fail-closed: só dispensa a confirmação para área conhecida com taxa zero."""
        encontrada = self.resolver(texto)
        return encontrada is None or encontrada.taxa > 0
