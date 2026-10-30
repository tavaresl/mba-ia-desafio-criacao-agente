"""Regras de autorização de visitantes (RN-03)."""

from aurora.contratos import (
    EntradaInvalida,
    MotivoInvalido,
    RepositorioVisitantes,
    ResultadoVisitante,
    Visitante,
    VisitanteAutorizado,
)
from aurora.dominio.validacao import interpretar_data, normalizar_nome_visitante

__all__ = ["ServicoVisitantesPadrao"]


class ServicoVisitantesPadrao:
    """Implementa `aurora.contratos.ServicoVisitantes`."""

    def __init__(self, *, visitantes: RepositorioVisitantes) -> None:
        self._visitantes = visitantes

    async def autorizar(self, *, apartamento: str, nome: str, data: str) -> ResultadoVisitante:
        nome_valido = normalizar_nome_visitante(nome)
        if nome_valido is None:
            return EntradaInvalida(MotivoInvalido.NOME_INVALIDO)
        dia = interpretar_data(data)
        if dia is None:
            return EntradaInvalida(MotivoInvalido.DATA_INVALIDA)
        await self._visitantes.autorizar(apartamento=apartamento, nome=nome_valido, data=dia)
        return VisitanteAutorizado(nome_valido, dia)

    async def listar_do_apartamento(self, apartamento: str) -> list[Visitante]:
        return await self._visitantes.listar(apartamento)
