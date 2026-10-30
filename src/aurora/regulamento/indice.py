"""Índice do regulamento por capítulo (ADR-015)."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

__all__ = ["CAPITULOS_ESPERADOS", "PADRAO_CAPITULO", "Capitulo", "IndiceRegulamento"]

PADRAO_CAPITULO = re.compile(r"^## Capítulo (?P<romano>[IVXLC]+): (?P<tema>.+)$", re.MULTILINE)
CAPITULOS_ESPERADOS = 14


@dataclass(frozen=True, slots=True)
class Capitulo:
    id: str
    titulo: str
    texto: str


def _slug(tema: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", tema).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento).strip("-")


class IndiceRegulamento:
    """Capítulos do regulamento, imutáveis e seguros para leitura concorrente."""

    def __init__(self, capitulos: tuple[Capitulo, ...]) -> None:
        self._capitulos = capitulos
        self._por_id = {c.id: c for c in capitulos}

    @classmethod
    def carregar(cls, caminho: Path) -> "IndiceRegulamento":
        """Divide o arquivo nos cabeçalhos de capítulo.

        Raises:
            ValueError: Se não houver exatamente 14 capítulos ou se os ids não forem únicos.
        """
        try:
            conteudo = caminho.read_text(encoding="utf-8")
        except FileNotFoundError as erro:
            raise ValueError(f"regulamento não encontrado: {caminho}") from erro
        marcas = list(PADRAO_CAPITULO.finditer(conteudo))
        capitulos = []
        for posicao, marca in enumerate(marcas):
            fim = marcas[posicao + 1].start() if posicao + 1 < len(marcas) else len(conteudo)
            capitulos.append(
                Capitulo(
                    id=f"{marca['romano']}-{_slug(marca['tema'])}",
                    titulo=f"Capítulo {marca['romano']}: {marca['tema']}",
                    texto=conteudo[marca.start() : fim].strip(),
                )
            )
        if len(capitulos) != CAPITULOS_ESPERADOS:
            raise ValueError(f"{caminho.name}: esperados {CAPITULOS_ESPERADOS} capítulos, encontrados {len(capitulos)}")
        if len({c.id for c in capitulos}) != len(capitulos):
            raise ValueError(f"{caminho.name}: identificadores de capítulo repetidos")
        return cls(tuple(capitulos))

    def capitulos(self) -> tuple[Capitulo, ...]:
        return self._capitulos

    def obter(self, capitulo_id: str) -> Capitulo | None:
        return self._por_id.get(capitulo_id)
