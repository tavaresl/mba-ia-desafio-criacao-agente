"""Contratos compartilhados entre as camadas. Importa apenas a biblioteca padrão."""

from aurora.contratos.conversa import *  # noqa: F403
from aurora.contratos.conversa import __all__ as _conversa
from aurora.contratos.modelos import *  # noqa: F403
from aurora.contratos.modelos import __all__ as _modelos
from aurora.contratos.repositorios import *  # noqa: F403
from aurora.contratos.repositorios import __all__ as _repositorios
from aurora.contratos.servicos import *  # noqa: F403
from aurora.contratos.servicos import __all__ as _servicos

__all__ = [*_modelos, *_repositorios, *_servicos, *_conversa]
