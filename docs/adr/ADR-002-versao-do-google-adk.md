# ADR-002 — Versão do Google ADK: fixar `google-adk[db]==2.13.0`

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Influencia:** [ADR-003](ADR-003-topologia-de-agentes.md), [ADR-004](ADR-004-controle-de-turno-e-transferencias.md), [ADR-005](ADR-005-mecanismo-de-confirmacao.md), [ADR-006](ADR-006-retomada-sem-resumability.md), [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md), [ADR-011](ADR-011-servico-de-sessao-persistente.md). Todos dependem de comportamentos do ADK verificados nesta versão.
  - **Referências:** [SUMMARY GT-01](../SUMMARY.md#10-gotchas), [PRD — Dependências](../PRD.md#dependências)

## Contexto

O enunciado exige o Google ADK **na série 2, versão ≥ 2.2.0, com versão exata fixada**. Ele também alerta que, nos testes dos autores (2.2.0 e 2.9.1), o roteamento da resposta de confirmação **mudou conforme a versão**, a topologia, os bloqueios de transferência, a configuração de retomada e o serviço de sessão.

Situação em 2026-10-30 (PyPI): a versão mais recente é a **2.13.0** (2026-10-23). Desde a 2.2.0 saíram mais de 20 releases na série 2.

A análise do código-fonte da 2.13.0 confirmou os comportamentos dos quais as demais decisões dependem:

- `agents/_agent_router.py` (`find_agent_to_run`): uma resposta de função enviada pelo usuário é roteada ao agente autor da chamada.
- `tools/agent_tool.py`: o `AgentTool` roda o agente numa sessão em memória descartada e não retoma chamadas de longa duração.
- `tools/function_tool.py`: o `require_confirmation` aceita predicado.
- `flows/llm_flows/tools/_confirmation.py`: valida a resposta de confirmação contra o histórico.

O `DatabaseSessionService` exige o extra `db` (SQLAlchemy async). `fastapi`, `uvicorn` e `aiosqlite` já são dependências diretas do pacote.

## Decisão

1. Fixar **`google-adk[db]==2.13.0`** no `pyproject.toml`, com o `uv.lock` versionado.
2. Usar **Python 3.12** (`requires-python = ">=3.12"` e `.python-version` com `3.12`).
3. **Atualizações de versão só de forma deliberada**, e sempre reexecutando a prova de conceito de confirmação. Ela consiste em aprovar uma ação com sessão persistida, antes e depois de reiniciar a API, e conferir o efeito pelas rotas de verificação.
4. Os comportamentos do ADK em que as decisões se apoiam ficam citados, com o arquivo-fonte, nos ADRs correspondentes, para facilitar a revalidação numa troca de versão.
5. **Caminho de contingência:** se a prova de conceito falhar na 2.13.0 e não houver correção pela topologia ([ADR-003](ADR-003-topologia-de-agentes.md) e [ADR-004](ADR-004-controle-de-turno-e-transferencias.md)), recuar para a **2.9.1**, a versão testada pelos autores, e depois para a 2.2.0.

## Alternativas consideradas

### A1. Fixar 2.2.0, a versão do curso
- **Prós:** alinhada ao material das aulas; é o piso exigido.
- **Contras:** perde mais de 20 releases de correções; a documentação atual (Context7, docs oficiais) descreve versões mais novas, e as APIs da série 2 evoluíram (`mode`, roteamento de retomada).
- **Motivo do descarte:** fica como segunda contingência.

### A2. Fixar 2.9.1, uma das versões testadas pelos autores
- **Prós:** os autores observaram nela uma combinação funcional com sessão em SQLite.
- **Contras:** os autores também relataram combinações que falharam nessa versão; não traz as correções posteriores.
- **Motivo do descarte:** fica como primeira contingência.

### A3. Faixa de versões (ex.: `>=2.2,<3`)
- **Prós:** recebe correções automaticamente.
- **Contras:** viola a exigência de versão exata; uma atualização silenciosa pode mudar o roteamento de confirmação.
- **Motivo do descarte:** não atende o requisito (CA-01).

## Consequências

### Positivas
- Ambiente reproduzível para o avaliador (`uv sync` determinístico).
- As decisões arquiteturais se apoiam em comportamento verificado no código da versão fixada.
- Alinhamento com a documentação mais atual.

### Negativas
- Distância maior do material do curso, então exemplos das aulas podem precisar de ajuste.
- Algumas APIs usadas são marcadas como experimentais ou desencorajadas (ex.: uso direto de `AgentTool`) e podem mudar em versões futuras.

### Trade-off explícito
Escolhe-se a versão mais recente e corrigida, aceitando divergir do material do curso e assumindo o ônus de validar por prova de conceito que a confirmação funciona nela.
