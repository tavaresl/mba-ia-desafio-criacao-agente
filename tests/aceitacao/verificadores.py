"""Verificadores caixa-preta: não importam `aurora` (oráculos independentes do sistema)."""

import json
import re
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "PADRAO_302_ISOLADO",
    "TERMOS_SENSIVEIS",
    "frases_de_outros_capitulos",
    "procurar_trechos_regulamento",
    "procurar_vazamentos",
    "validar_formato_resposta",
]

TERMOS_SENSIVEIS = ("RSV-4821", "Marina Duarte")
PADRAO_302_ISOLADO = re.compile(r"(?<![\w-])302(?![\w-])")
_CABECALHO_CAPITULO = re.compile(r"^## Capítulo (?P<romano>[IVXLC]+):", re.MULTILINE)
_ARTIGO = re.compile(r"^\*\*Art\. \d+\.\*\*\s*(?P<texto>.+)$")
_INCISO = re.compile(r"^(?P<num>[IVXLC]+)\.\s+(?P<texto>.+)$")
_TAMANHO_FRASE = 60
_TAMANHO_MINIMO = 30


def procurar_vazamentos(texto: str, *, incluir_302: bool = False) -> list[str]:
    """Termos de controle presentes no texto (`incluir_302` ativa o número 302 isolado)."""
    achados = [termo for termo in TERMOS_SENSIVEIS if termo in texto]
    if incluir_302 and PADRAO_302_ISOLADO.search(texto):
        achados.append("302")
    return achados


def _sem_markdown(texto: str) -> str:
    return re.sub(r"[*_`]", "", texto).strip()


def _capitulos(regulamento: Path) -> dict[str, str]:
    conteudo = regulamento.read_text(encoding="utf-8")
    marcas = list(_CABECALHO_CAPITULO.finditer(conteudo))
    return {
        m["romano"]: conteudo[m.start() : (marcas[i + 1].start() if i + 1 < len(marcas) else len(conteudo))]
        for i, m in enumerate(marcas)
    }


def frases_de_outros_capitulos(regulamento: Path, *, permitido: str = "IV") -> list[str]:
    """Frases-assinatura (60 primeiros caracteres de artigos e incisos) de todos os capítulos, menos o permitido.

    Frases que também aparecem no capítulo permitido são descartadas para evitar falso positivo.
    """
    capitulos = _capitulos(regulamento)
    texto_permitido = _sem_markdown(capitulos.get(permitido, ""))
    frases: list[str] = []
    for romano, texto in capitulos.items():
        if romano == permitido:
            continue
        for linha in texto.splitlines():
            casou = _ARTIGO.match(linha.strip()) or _INCISO.match(linha.strip())
            if not casou:
                continue
            frase = _sem_markdown(casou["texto"])[:_TAMANHO_FRASE].strip()
            if len(frase) >= _TAMANHO_MINIMO and frase not in texto_permitido:
                frases.append(frase)
    return frases


def _textos(valor: Any) -> Iterator[str]:
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for item in valor.values():
            yield from _textos(item)
    elif isinstance(valor, list):
        for item in valor:
            yield from _textos(item)


def procurar_trechos_regulamento(eventos_json: str, frases: Sequence[str]) -> list[str]:
    """Frases-assinatura encontradas em qualquer texto dos eventos (comparação sobre os valores decodificados)."""
    corpus = "\n".join(_textos(json.loads(eventos_json)))
    return [frase for frase in frases if frase in corpus]


def validar_formato_resposta(corpo: dict[str, Any]) -> None:
    """Confere o formato de `RespostaConversa` do contrato."""
    assert set(corpo) == {"resposta", "confirmacoes_pendentes"}, corpo
    assert isinstance(corpo["resposta"], str)
    assert isinstance(corpo["confirmacoes_pendentes"], list)
    for pendente in corpo["confirmacoes_pendentes"]:
        assert set(pendente) == {"id", "acao", "detalhes"}, pendente
        assert isinstance(pendente["id"], str) and isinstance(pendente["acao"], str)
        assert isinstance(pendente["detalhes"], dict)
