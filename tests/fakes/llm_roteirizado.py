"""LLM roteirizado: respostas pré-definidas, sem chamar o Gemini."""

from collections.abc import AsyncGenerator, Callable
from typing import Any

from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.models._capabilities import LlmCapabilities
from google.genai import types

Passo = LlmResponse | Callable[[LlmRequest], LlmResponse]


def texto(conteudo: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=conteudo)]))


def chamada(nome: str, **argumentos: Any) -> LlmResponse:
    return LlmResponse(
        content=types.Content(
            role="model", parts=[types.Part(function_call=types.FunctionCall(name=nome, args=argumentos))]
        )
    )


class RoteiroLlm(BaseLlm):
    """Devolve os passos em ordem; cada passo pode ser uma resposta ou uma função da requisição."""

    model: str = "roteirizado"
    passos: list[Any] = []
    requisicoes: list[Any] = []

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=False)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.requisicoes.append(llm_request)
        if not self.passos:
            raise AssertionError("roteiro esgotado: chamada inesperada ao modelo")
        passo = self.passos.pop(0)
        yield passo(llm_request) if callable(passo) else passo
