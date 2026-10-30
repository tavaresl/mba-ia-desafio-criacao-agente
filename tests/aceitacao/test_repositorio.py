"""Checagens objetivas do passo 15 (repositório)."""

import re
import subprocess
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PADRAO_CHAVE = re.compile(r"AIza[0-9A-Za-z_\-]{30,}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout


def test_adk_fixado_com_versao_exata_na_serie_2() -> None:
    dependencias = tomllib.loads((RAIZ / "pyproject.toml").read_text())["project"]["dependencies"]
    (adk,) = [d for d in dependencias if d.startswith("google-adk")]
    versao = re.fullmatch(r"google-adk(\[\w+\])?==(\d+)\.(\d+)\.(\d+)", adk)
    assert versao, adk
    assert (int(versao[2]), int(versao[3])) >= (2, 2) and versao[2] == "2"
    assert "google-adk" in (RAIZ / "uv.lock").read_text()


def test_dados_identicos_ao_repositorio_base() -> None:
    commit_base = _git("log", "--diff-filter=A", "--format=%H", "--", "dados/reservas.json").split()[-1]
    assert _git("diff", commit_base, "--", "dados") == ""
    assert _git("status", "--porcelain", "dados") == ""


def test_nenhuma_chave_versionada_e_env_fora_do_git() -> None:
    assert _git("ls-files", ".env").strip() == ""
    for arquivo in _git("ls-files").split():
        caminho = RAIZ / arquivo
        if caminho.suffix in {".png", ".lock"} or not caminho.is_file():
            continue
        assert not PADRAO_CHAVE.search(caminho.read_text(errors="ignore")), f"possível chave em {arquivo}"


def test_env_example_lista_nomes_sem_valores() -> None:
    linhas = [linha for linha in (RAIZ / ".env.example").read_text().splitlines() if linha.strip()]
    nomes = {linha.split("=")[0] for linha in linhas}
    assert {"GOOGLE_API_KEY", "AURORA_MODELO"} <= nomes
    assert all(linha.split("=", 1)[1] == "" for linha in linhas)
