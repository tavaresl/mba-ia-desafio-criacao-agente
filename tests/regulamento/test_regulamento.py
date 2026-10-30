import json
from pathlib import Path

import pytest
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from aurora.config import carregar_configuracoes
from aurora.regulamento import IndiceRegulamento, criar_ferramenta_regulamento
from aurora.regulamento.ferramenta_capitulo import criar_ferramenta_capitulo
from aurora.regulamento.instrucoes import montar_instrucoes
from tests.fakes.llm_roteirizado import RoteiroLlm, chamada, texto

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = carregar_configuracoes(RAIZ, exigir_chave=False)


@pytest.fixture(scope="module")
def indice() -> IndiceRegulamento:
    return IndiceRegulamento.carregar(RAIZ / "dados" / "regulamento.md")


def test_indice_tem_14_capitulos(indice: IndiceRegulamento) -> None:
    capitulos = indice.capitulos()
    assert len(capitulos) == 14
    assert capitulos[3].id == "IV-piscina"
    assert capitulos[5].id == "VI-salao-de-festas-churrasqueira-e-quadra"
    assert len({c.id for c in capitulos}) == 14


def test_capitulo_iv_vai_do_cabecalho_ao_proximo(indice: IndiceRegulamento) -> None:
    piscina = indice.obter("IV-piscina")
    assert piscina.texto.startswith("## Capítulo IV: Piscina")
    assert "Art. 22." in piscina.texto and "das 9h às 20h" in piscina.texto
    assert "Capítulo V" not in piscina.texto and "Art. 29." not in piscina.texto
    assert "período de silêncio" not in piscina.texto.lower()


def test_indice_invalido(tmp_path: Path) -> None:
    arquivo = tmp_path / "r.md"
    arquivo.write_text("## Capítulo I: Único\n\ntexto")
    with pytest.raises(ValueError, match="14 capítulos"):
        IndiceRegulamento.carregar(arquivo)
    with pytest.raises(ValueError, match="não encontrado"):
        IndiceRegulamento.carregar(tmp_path / "nada.md")


async def test_ferramenta_devolve_um_capitulo_ou_erro_sem_texto(indice: IndiceRegulamento) -> None:
    ferramenta = criar_ferramenta_capitulo(indice)
    ok = await ferramenta.func(capitulo="IV-piscina")
    assert ok["capitulo"] == "IV-piscina" and "Art. 22." in ok["texto"]
    assert await ferramenta.func(capitulo="XX-inventado") == {"erro": "capitulo_inexistente"}


def test_declaracao_da_tool_restringe_o_capitulo_a_um_enum(indice: IndiceRegulamento) -> None:
    declaracao = criar_ferramenta_capitulo(indice)._get_declaration()
    esquema = json.dumps(declaracao.model_dump(mode="json", exclude_none=True), ensure_ascii=False)
    assert "IV-piscina" in esquema and "XIV-" in esquema


def test_instrucoes_listam_titulos_mas_nao_o_texto(indice: IndiceRegulamento) -> None:
    instrucoes = montar_instrucoes(indice)
    assert "IV-piscina: Capítulo IV: Piscina" in instrucoes
    assert "das 9h às 20h" not in instrucoes and "Art. 22" not in instrucoes


async def test_isolamento_eventos_da_sessao_principal_nao_contem_texto_de_capitulos(indice: IndiceRegulamento) -> None:
    especialista_llm = RoteiroLlm(
        passos=[
            chamada("consultar_capitulo", capitulo="IV-piscina"),
            texto("Aos domingos e feriados a piscina funciona das 9h às 20h (Art. 22, II)."),
        ],
        requisicoes=[],
    )
    ferramenta = criar_ferramenta_regulamento(configuracoes=CONFIG, indice=indice, modelo=especialista_llm)
    principal_llm = RoteiroLlm(
        passos=[
            chamada("regulamento", request="Até que horas a piscina funciona aos domingos?"),
            texto("A piscina fecha às 20h aos domingos."),
        ],
        requisicoes=[],
    )
    concierge = LlmAgent(name="concierge", model=principal_llm, instruction="Delegue.", tools=[ferramenta])
    servico = InMemorySessionService()
    runner = Runner(app=App(name="t", root_agent=concierge), session_service=servico)
    sessao = await servico.create_session(app_name="t", user_id="101")
    async for _ in runner.run_async(
        user_id="101", session_id=sessao.id, new_message=types.Content(role="user", parts=[types.Part(text="piscina?")])
    ):
        pass
    eventos = (await servico.get_session(app_name="t", user_id="101", session_id=sessao.id)).events
    bruto = json.dumps([e.model_dump(mode="json", exclude_none=True) for e in eventos], ensure_ascii=False)
    assert "20h" in bruto
    assert "Art. 23." not in bruto and "exame dermatológico" not in bruto  # texto bruto do capítulo IV
    assert "período de silêncio" not in bruto.lower()
    assert any(e.get_function_calls() and e.get_function_calls()[0].name == "regulamento" for e in eventos)
    assert not any(c.name == "consultar_capitulo" for e in eventos for c in e.get_function_calls())
