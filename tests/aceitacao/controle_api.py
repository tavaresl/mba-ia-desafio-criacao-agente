"""Controle da API real como subprocesso e cliente HTTP com tolerância a cota (ERRO_INFRA)."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

RAIZ = Path(__file__).resolve().parents[2]
BASE_URL = "http://localhost:8000"
TIMEOUT_S = float(os.environ.get("AURORA_ACEITACAO_TIMEOUT_S", "120"))
ESPERA_SUBIDA_S = 30
PERGUNTA_PADRAO = "Sim, pode seguir com os dados que informei."


class ControleApi:
    """Sobe e derruba `aurora-api` como um processo à parte, como faria o avaliador."""

    def __init__(self, log: Path) -> None:
        self._log = log
        self._processo: subprocess.Popen[bytes] | None = None
        self.cliente = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_S)

    @staticmethod
    def porta_ocupada() -> bool:
        with socket.socket() as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", 8000)) == 0

    def restaurar(self) -> None:
        resultado = subprocess.run(
            [sys.executable, "-c", "from aurora.ciclo_de_vida.cli import main; main()"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
        )
        assert resultado.returncode == 0, f"restauração falhou: {resultado.stderr}"

    def subir(self) -> None:
        if self.porta_ocupada():
            pytest.fail("porta 8000 ocupada: pare a API que está rodando antes do roteiro")
        saida = self._log.open("ab")
        self._processo = subprocess.Popen(
            [sys.executable, "-c", "from aurora.api.cli import main; main()"], cwd=RAIZ, stdout=saida, stderr=saida
        )
        limite = time.monotonic() + ESPERA_SUBIDA_S
        while time.monotonic() < limite:
            if self._processo.poll() is not None:
                break
            try:
                if self.cliente.get("/apartamentos/101/reservas", timeout=2).status_code == 200:
                    return
            except httpx.TransportError:
                time.sleep(0.5)
        pytest.fail(f"a API não subiu em {ESPERA_SUBIDA_S}s; log:\n{self._log.read_text(errors='replace')[-2000:]}")

    def parar(self) -> None:
        if self._processo and self._processo.poll() is None:
            self._processo.send_signal(signal.SIGINT)  # equivale ao Ctrl+C
            try:
                self._processo.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self._processo.kill()
        self._processo = None

    def reiniciar(self) -> None:
        self.parar()
        self.subir()

    def subir_do_zero(self) -> None:
        self.parar()
        self.restaurar()
        self.subir()

    # --- chamadas HTTP ---
    def requisitar(self, metodo: str, rota: str, **kwargs: Any) -> httpx.Response:
        """Uma nova tentativa após espera quando o modelo está indisponível (503); persistindo, é ERRO_INFRA."""
        resposta = self.cliente.request(metodo, rota, **kwargs)
        if resposta.status_code == 503:
            time.sleep(20)
            resposta = self.cliente.request(metodo, rota, **kwargs)
        if resposta.status_code == 503:
            pytest.fail(f"ERRO_INFRA: 503 persistente em {metodo} {rota} (cota ou indisponibilidade do modelo)")
        return resposta

    def criar_sessao(self, apartamento: str) -> str:
        resposta = self.requisitar("POST", "/sessoes", json={"apartamento": apartamento})
        assert resposta.status_code == 201, resposta.text
        return resposta.json()["session_id"]

    def mensagem(self, sid: str, texto: str) -> dict[str, Any]:
        resposta = self.requisitar("POST", f"/sessoes/{sid}/mensagens", json={"texto": texto})
        assert resposta.status_code == 200, resposta.text
        return resposta.json()

    def confirmar(self, sid: str, id_: str, confirmado: bool) -> httpx.Response:
        return self.requisitar("POST", f"/sessoes/{sid}/confirmacoes", json={"id": id_, "confirmado": confirmado})

    def eventos(self, sid: str) -> list[dict[str, Any]]:
        resposta = self.requisitar("GET", f"/sessoes/{sid}/eventos")
        assert resposta.status_code == 200, resposta.text
        return resposta.json()

    def reservas(self, apartamento: str) -> list[dict[str, str]]:
        return self.requisitar("GET", f"/apartamentos/{apartamento}/reservas").json()

    def visitantes(self, apartamento: str) -> list[dict[str, str]]:
        return self.requisitar("GET", f"/apartamentos/{apartamento}/visitantes").json()

    def pedir_ate_pendencia(self, sid: str, texto: str) -> dict[str, Any]:
        """Envia o pedido; se o assistente só fizer uma pergunta, responde uma vez com a resposta padrão."""
        resposta = self.mensagem(sid, texto)
        if not resposta["confirmacoes_pendentes"] and "?" in resposta["resposta"]:
            resposta = self.mensagem(sid, PERGUNTA_PADRAO)
        return resposta
