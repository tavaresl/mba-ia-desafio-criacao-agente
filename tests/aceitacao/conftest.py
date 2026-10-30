import os
from collections.abc import Iterator

import pytest
from dotenv import load_dotenv

from tests.aceitacao.controle_api import RAIZ, ControleApi

load_dotenv(RAIZ / ".env", override=False)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """A suíte consome cota do Gemini: só roda com AURORA_ACEITACAO=1 e GOOGLE_API_KEY definidas."""
    habilitada = os.environ.get("AURORA_ACEITACAO") == "1" and bool(os.environ.get("GOOGLE_API_KEY"))
    for item in items:
        if "aceitacao" in item.keywords and not habilitada:
            item.add_marker(pytest.mark.skip(reason="defina AURORA_ACEITACAO=1 e GOOGLE_API_KEY"))


@pytest.fixture(scope="session")
def api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ControleApi]:
    controle = ControleApi(tmp_path_factory.mktemp("api") / "api.log")
    controle.subir_do_zero()
    yield controle
    controle.parar()
