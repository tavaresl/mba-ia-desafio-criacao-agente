"""Rotas de verificação: leem o domínio direto, sem o modelo (em produção ficariam atrás de acesso administrativo)."""

from fastapi import APIRouter, Request

from aurora.api.esquemas import ReservaSaida, VisitanteSaida

__all__ = ["roteador_verificacao"]

roteador_verificacao = APIRouter(prefix="/apartamentos", tags=["verificação"])


@roteador_verificacao.get("/{numero}/reservas", response_model=list[ReservaSaida])
async def reservas_do_apartamento(numero: str, request: Request) -> list[ReservaSaida]:
    reservas = await request.app.state.aplicacao.reservas.listar_do_apartamento(numero)
    return [ReservaSaida(codigo=r.codigo, area=r.area_id, data=r.data.isoformat()) for r in reservas]


@roteador_verificacao.get("/{numero}/visitantes", response_model=list[VisitanteSaida])
async def visitantes_do_apartamento(numero: str, request: Request) -> list[VisitanteSaida]:
    visitantes = await request.app.state.aplicacao.visitantes.listar_do_apartamento(numero)
    return [VisitanteSaida(nome=v.nome, data=v.data.isoformat()) for v in visitantes]
