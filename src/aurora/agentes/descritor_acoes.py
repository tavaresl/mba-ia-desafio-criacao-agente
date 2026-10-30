"""Traduz uma chamada de tool pendente em `acao` e `detalhes` da API."""

from collections.abc import Mapping
from typing import Any

from aurora.contratos import ACAO_AUTORIZAR_VISITANTE, ACAO_RESERVAR_AREA, ServicoReservas

__all__ = ["DescritorAcoesPadrao"]


class DescritorAcoesPadrao:
    """Implementa `aurora.contratos.DescritorAcoes`, usando a mesma resolução de área do predicado."""

    def __init__(self, servico_reservas: ServicoReservas) -> None:
        self._reservas = servico_reservas

    def descrever(self, nome_tool: str, argumentos: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        if nome_tool == ACAO_RESERVAR_AREA:
            texto_area = str(argumentos.get("area", ""))
            area = self._reservas.resolver_area(texto_area)
            detalhes: dict[str, Any] = {"area": area.id if area else texto_area}
            if area:
                detalhes |= {"area_nome": area.nome, "taxa": f"{area.taxa:.2f}"}
            detalhes["data"] = argumentos.get("data")
            return ACAO_RESERVAR_AREA, detalhes
        if nome_tool == ACAO_AUTORIZAR_VISITANTE:
            return ACAO_AUTORIZAR_VISITANTE, {"nome": argumentos.get("nome"), "data": argumentos.get("data")}
        return nome_tool, dict(argumentos)
