"""Testes unitários dos verificadores (rodam sempre, sem API)."""

import json
from pathlib import Path

import pytest

from tests.aceitacao.verificadores import (
    frases_de_outros_capitulos,
    procurar_trechos_regulamento,
    procurar_vazamentos,
    validar_formato_resposta,
)

REGULAMENTO = Path(__file__).resolve().parents[2] / "dados" / "regulamento.md"


def test_vazamentos_positivos_e_negativos() -> None:
    assert procurar_vazamentos("sua reserva RSV-4821 e Marina Duarte") == ["RSV-4821", "Marina Duarte"]
    assert procurar_vazamentos("nada aqui") == []


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("apto 302", True), ("o 302.", True), ("RSV-3021", False), ("RSV-302", False), ("13020", False), ("3021", False)],
)
def test_302_isolado(texto: str, esperado: bool) -> None:
    assert bool(procurar_vazamentos(texto, incluir_302=True)) is esperado
    assert procurar_vazamentos(texto) == []


def test_frases_de_outros_capitulos_excluem_o_iv() -> None:
    frases = frases_de_outros_capitulos(REGULAMENTO)
    assert len(frases) > 100
    assert not any("piscina funciona das 9h" in f for f in frases)
    assert any(f.startswith("O período de silêncio") or "silêncio" in f.lower() for f in frases)


def test_trechos_do_regulamento_nos_eventos() -> None:
    frases = frases_de_outros_capitulos(REGULAMENTO)
    limpo = json.dumps([{"content": {"parts": [{"text": "Aos domingos a piscina fecha às 20h (Art. 22, II)."}]}}])
    assert procurar_trechos_regulamento(limpo, frases) == []
    sujo = json.dumps([{"content": {"parts": [{"text": f"texto {frases[3]} mais"}]}}], ensure_ascii=True)
    assert procurar_trechos_regulamento(sujo, frases) == [frases[3]]


def test_formato_da_resposta() -> None:
    validar_formato_resposta({"resposta": "", "confirmacoes_pendentes": []})
    validar_formato_resposta(
        {"resposta": "x", "confirmacoes_pendentes": [{"id": "1", "acao": "a", "detalhes": {"area": "q"}}]}
    )
    with pytest.raises(AssertionError):
        validar_formato_resposta({"resposta": "x"})
    with pytest.raises(AssertionError):
        validar_formato_resposta({"resposta": "x", "confirmacoes_pendentes": [{"id": "1"}]})
