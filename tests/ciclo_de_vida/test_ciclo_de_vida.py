import hashlib
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from aurora.ciclo_de_vida import DadosIniciaisInvalidos, carregar_dados_iniciais, preparar_banco, restaurar
from aurora.infra import criar_engine_sqlite
from aurora.persistencia import criar_repositorios
from tests.fakes import (
    IndiceSessoesEmMemoria,
    RepositorioCargaInicialEmMemoria,
    RepositorioReservasEmMemoria,
    RepositorioVisitantesEmMemoria,
)

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "dados"


def _hashes(diretorio: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(diretorio.iterdir())}


def test_carrega_dados_reais() -> None:
    dados = carregar_dados_iniciais(DADOS)
    assert [r.codigo for r in dados.reservas] == ["RSV-1377", "RSV-4821", "RSV-2950"]
    assert {a.id: int(a.taxa) for a in dados.areas}["quadra"] == 0
    assert dados.visitantes[0].nome == "Marina Duarte"


@pytest.mark.parametrize(
    ("arquivo", "conteudo"),
    [
        ("reservas.json", "{nao e json"),
        ("reservas.json", '[{"codigo": "X", "apartamento": "999", "area": "quadra", "data": "2030-01-01"}]'),
        ("reservas.json", '[{"codigo": "X", "apartamento": "101", "area": "quadra", "data": "2030-13-01"}]'),
        ("visitantes.json", '[{"apartamento": "101", "nome": "A"}]'),
        ("areas.json", '{"id": "x"}'),
    ],
)
def test_json_invalido(tmp_path: Path, arquivo: str, conteudo: str) -> None:
    shutil.copytree(DADOS, tmp_path / "dados")
    (tmp_path / "dados" / arquivo).write_text(conteudo)
    with pytest.raises(DadosIniciaisInvalidos, match=arquivo):
        carregar_dados_iniciais(tmp_path / "dados")


def test_duas_reservas_na_mesma_area_e_data_sao_invalidas(tmp_path: Path) -> None:
    shutil.copytree(DADOS, tmp_path / "dados")
    (tmp_path / "dados" / "reservas.json").write_text(
        '[{"codigo": "A", "apartamento": "101", "area": "quadra", "data": "2030-01-01"},'
        ' {"codigo": "B", "apartamento": "201", "area": "quadra", "data": "2030-01-01"}]'
    )
    with pytest.raises(DadosIniciaisInvalidos, match="mesma área e data"):
        carregar_dados_iniciais(tmp_path / "dados")


async def test_preparar_banco_so_aplica_seed_uma_vez() -> None:
    reservas, visitantes = RepositorioReservasEmMemoria(), RepositorioVisitantesEmMemoria()
    carga = RepositorioCargaInicialEmMemoria(reservas, visitantes)
    leituras: list[int] = []

    def fabrica():
        leituras.append(1)
        return carregar_dados_iniciais(DADOS)

    assert await preparar_banco(carga, fabrica) is True
    for r in list(reservas.ativas):  # mesmo com tudo cancelado, não restaura de novo
        del reservas.ativas[r]
    assert await preparar_banco(carga, fabrica) is False
    assert reservas.ativas == {} and len(leituras) == 1


async def test_restaurar_limpa_indice_e_arquivo_de_sessoes(tmp_path: Path) -> None:
    reservas, visitantes = RepositorioReservasEmMemoria(), RepositorioVisitantesEmMemoria()
    indice = IndiceSessoesEmMemoria()
    await indice.registrar(session_id="s", apartamento="101")
    banco = tmp_path / "sessions.db"
    for sufixo in ("", "-wal", "-shm"):
        Path(f"{banco}{sufixo}").write_text("x")
    resumo = await restaurar(
        carga=RepositorioCargaInicialEmMemoria(reservas, visitantes),
        indice_sessoes=indice,
        banco_sessoes=banco,
        dados=carregar_dados_iniciais(DADOS),
    )
    assert (resumo.reservas, resumo.visitantes, resumo.sessoes_apagadas) == (3, 2, True)
    assert indice.itens == {} and not list(tmp_path.iterdir())


async def test_restaurar_com_sqlite_preserva_codigos_emitidos(tmp_path: Path) -> None:
    engine = criar_engine_sqlite(tmp_path / "d.db", busy_timeout_ms=5000)
    repos = criar_repositorios(engine)
    dados = carregar_dados_iniciais(DADOS)
    kwargs = {"carga": repos.carga, "indice_sessoes": repos.sessoes, "banco_sessoes": tmp_path / "s.db", "dados": dados}
    await restaurar(**kwargs)
    await repos.reservas.criar(
        apartamento="101", area_id="quadra", data=date(2030, 9, 9), gerar_codigo=lambda: "NOVO-1"
    )
    await restaurar(**kwargs)  # idempotente
    assert [r.codigo for r in await repos.reservas.listar_ativas("101")] == ["RSV-1377"]
    with pytest.raises(RuntimeError):
        await repos.reservas.criar(
            apartamento="101", area_id="quadra", data=date(2030, 9, 9), gerar_codigo=lambda: "NOVO-1"
        )
    await engine.dispose()


def test_cli_em_clone_limpo_nao_altera_dados_e_falha_com_json_invalido(tmp_path: Path) -> None:
    raiz = tmp_path / "proj"
    shutil.copytree(DADOS, raiz / "dados")
    antes = _hashes(raiz / "dados")
    codigo = (
        "import sys; from pathlib import Path; import aurora.config as c; "
        f"r = Path({str(raiz)!r}); "
        "orig = c.carregar_configuracoes; c.carregar_configuracoes = lambda **k: orig(r, **k); "
        "import aurora.ciclo_de_vida.cli as cli; cli.carregar_configuracoes = c.carregar_configuracoes; cli.main()"
    )
    ok = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=RAIZ)
    assert ok.returncode == 0, ok.stderr
    assert "3 reservas, 2 visitantes" in ok.stdout
    assert (raiz / "var" / "aurora.db").exists()
    assert _hashes(raiz / "dados") == antes
    (raiz / "dados" / "reservas.json").write_text("[")
    ruim = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=RAIZ)
    assert ruim.returncode == 1 and "reservas.json" in ruim.stderr


def test_dados_do_repositorio_nao_foram_alterados() -> None:
    saida = subprocess.run(["git", "status", "--porcelain", "dados"], capture_output=True, text=True, cwd=RAIZ)
    assert saida.stdout.strip() == ""
