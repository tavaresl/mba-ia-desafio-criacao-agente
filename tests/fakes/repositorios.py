"""Fakes em memória dos repositórios (mesma suíte de contrato que a implementação SQLite)."""

from collections.abc import Callable
from datetime import date

from aurora.contratos import (
    Area,
    DadosIniciais,
    Indisponivel,
    NaoEncontrada,
    Reserva,
    ReservaCancelada,
    ReservaCriada,
    Visitante,
)


class RepositorioReservasEmMemoria:
    def __init__(self) -> None:
        self.ativas: dict[str, Reserva] = {}
        self.codigos_emitidos: set[str] = set()

    def _cancelar(self, reserva: Reserva | None) -> ReservaCancelada | NaoEncontrada:
        if reserva is None:
            return NaoEncontrada()
        del self.ativas[reserva.codigo]
        return ReservaCancelada(reserva.codigo, reserva.area_id, reserva.data)

    async def criar(
        self, *, apartamento: str, area_id: str, data: date, gerar_codigo: Callable[[], str]
    ) -> ReservaCriada | Indisponivel:
        if await self.esta_ocupada(area_id=area_id, data=data):
            return Indisponivel(area_id, data)
        for _ in range(5):
            codigo = gerar_codigo()
            if codigo not in self.codigos_emitidos:
                break
        else:
            raise RuntimeError("não foi possível gerar um código único")
        self.codigos_emitidos.add(codigo)
        self.ativas[codigo] = Reserva(codigo, apartamento, area_id, data)
        return ReservaCriada(codigo, area_id, data)

    async def cancelar_ativa(self, *, apartamento: str, area_id: str, data: date) -> ReservaCancelada | NaoEncontrada:
        alvo = next(
            (r for r in self.ativas.values() if (r.apartamento, r.area_id, r.data) == (apartamento, area_id, data)),
            None,
        )
        return self._cancelar(alvo)

    async def cancelar_por_codigo(self, *, apartamento: str, codigo: str) -> ReservaCancelada | NaoEncontrada:
        reserva = self.ativas.get(codigo)
        return self._cancelar(reserva if reserva and reserva.apartamento == apartamento else None)

    async def listar_ativas(self, apartamento: str) -> list[Reserva]:
        return sorted(
            (r for r in self.ativas.values() if r.apartamento == apartamento), key=lambda r: (r.data, r.codigo)
        )

    async def esta_ocupada(self, *, area_id: str, data: date) -> bool:
        return any(r.area_id == area_id and r.data == data for r in self.ativas.values())


class RepositorioVisitantesEmMemoria:
    def __init__(self) -> None:
        self.itens: list[Visitante] = []

    async def autorizar(self, *, apartamento: str, nome: str, data: date) -> Visitante:
        visitante = Visitante(apartamento, nome, data)
        self.itens.append(visitante)
        return visitante

    async def listar(self, apartamento: str) -> list[Visitante]:
        return sorted((v for v in self.itens if v.apartamento == apartamento), key=lambda v: v.data)


class CatalogoReferenciaEmMemoria:
    def __init__(self, areas: list[Area], apartamentos: list[str]) -> None:
        self._areas = areas
        self._apartamentos = set(apartamentos)

    async def listar_areas(self) -> list[Area]:
        return list(self._areas)

    async def apartamento_existe(self, numero: str) -> bool:
        return numero in self._apartamentos


class IndiceSessoesEmMemoria:
    def __init__(self) -> None:
        self.itens: dict[str, str] = {}

    async def registrar(self, *, session_id: str, apartamento: str) -> None:
        self.itens[session_id] = apartamento

    async def apartamento_de(self, session_id: str) -> str | None:
        return self.itens.get(session_id)

    async def remover(self, session_id: str) -> None:
        self.itens.pop(session_id, None)

    async def limpar(self) -> None:
        self.itens.clear()


class RepositorioCargaInicialEmMemoria:
    def __init__(self, reservas: RepositorioReservasEmMemoria, visitantes: RepositorioVisitantesEmMemoria) -> None:
        self._reservas = reservas
        self._visitantes = visitantes
        self.esquema_criado = False
        self.aplicado = False

    async def criar_esquema(self) -> None:
        self.esquema_criado = True

    async def seed_aplicado(self) -> bool:
        return self.aplicado

    async def restaurar(self, dados: DadosIniciais) -> None:
        self._reservas.ativas = {r.codigo: r for r in dados.reservas}
        self._reservas.codigos_emitidos |= {r.codigo for r in dados.reservas}
        self._visitantes.itens = list(dados.visitantes)
        self.aplicado = True
