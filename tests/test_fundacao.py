"""Critérios do FDD-01: isolamento de imports, __all__ e pragmas do SQLite."""

import ast
import tomllib
from pathlib import Path

import pytest
from sqlalchemy import text

from aurora.config import carregar_configuracoes
from aurora.infra import criar_engine_sqlite

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "aurora"
PROIBIDOS_NOS_CONTRATOS = ("google", "sqlalchemy", "fastapi")


def _imports(arquivo: Path) -> set[str]:
    nomes: set[str] = set()
    for no in ast.walk(ast.parse(arquivo.read_text())):
        if isinstance(no, ast.Import):
            nomes |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module)
    return nomes


@pytest.mark.parametrize("pacote", ["contratos", "dominio"])
def test_pacote_puro_nao_importa_frameworks(pacote: str) -> None:
    for arquivo in (SRC / pacote).glob("*.py"):
        for nome in _imports(arquivo):
            assert nome.split(".")[0] not in PROIBIDOS_NOS_CONTRATOS, f"{arquivo.name} importa {nome}"


def test_todo_pacote_tem_all_explicito() -> None:
    for init in SRC.rglob("__init__.py"):
        assert "__all__" in init.read_text(), f"{init} sem __all__"


def test_sem_imports_relativos() -> None:
    for arquivo in SRC.rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text())):
            assert not (isinstance(no, ast.ImportFrom) and no.level), f"import relativo em {arquivo}"


def test_adk_fixado_com_versao_exata() -> None:
    deps = tomllib.loads((RAIZ / "pyproject.toml").read_text())["project"]["dependencies"]
    assert any(d.startswith("google-adk[db]==2.") for d in deps)


def test_chave_obrigatoria(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match=".env.example"):
        carregar_configuracoes(tmp_path)
    assert carregar_configuracoes(tmp_path, exigir_chave=False).banco_dominio == tmp_path / "var" / "aurora.db"


async def test_engine_aplica_pragmas_em_conexoes_novas(tmp_path: Path) -> None:
    engine = criar_engine_sqlite(tmp_path / "v" / "t.db", busy_timeout_ms=1234)
    for _ in range(2):
        async with engine.connect() as conexao:
            assert (await conexao.execute(text("PRAGMA journal_mode"))).scalar() == "wal"
            assert (await conexao.execute(text("PRAGMA busy_timeout"))).scalar() == 1234
            assert (await conexao.execute(text("PRAGMA foreign_keys"))).scalar() == 1
    await engine.dispose()
