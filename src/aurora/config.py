"""Configuração da aplicação: variáveis de ambiente e caminhos."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

__all__ = ["Configuracoes", "carregar_configuracoes", "MODELO_PADRAO"]

MODELO_PADRAO = "gemini-3.8-flash"


@dataclass(frozen=True, slots=True)
class Configuracoes:
    """Configuração imutável, injetada por construtor nas demais camadas."""

    raiz_projeto: Path
    diretorio_dados: Path
    banco_dominio: Path
    banco_sessoes: Path
    nome_app: str = "residencial_aurora"
    modelo: str = MODELO_PADRAO
    temperatura: float = 0.1
    sqlite_busy_timeout_ms: int = 15000
    host: str = "127.0.0.1"
    porta: int = 8000


def _raiz_padrao() -> Path:
    return Path(__file__).resolve().parents[2]


def carregar_configuracoes(raiz: Path | None = None, *, exigir_chave: bool = True) -> Configuracoes:
    """Carrega o `.env` e monta as configurações.

    Args:
        raiz: Raiz do projeto. Por padrão, a raiz do repositório.
        exigir_chave: Se verdadeiro, exige `GOOGLE_API_KEY` (o comando de restauração não precisa dela).

    Raises:
        ValueError: Se a chave for exigida e não estiver definida.
    """
    raiz = (raiz or _raiz_padrao()).resolve()
    load_dotenv(raiz / ".env", override=False)
    if exigir_chave and not os.environ.get("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY não definida: copie .env.example para .env e preencha a chave.")
    return Configuracoes(
        raiz_projeto=raiz,
        diretorio_dados=raiz / "dados",
        banco_dominio=raiz / "var" / "aurora.db",
        banco_sessoes=raiz / "var" / "sessions.db",
        modelo=os.environ.get("AURORA_MODELO") or MODELO_PADRAO,
    )
