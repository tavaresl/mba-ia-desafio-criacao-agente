# ADR-017 — API em FastAPI com processo único, `Runner` compartilhado e serialização por sessão

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md) (pendências e `409`), [ADR-009](ADR-009-identidade-do-apartamento.md) (resolução de sessão e `404`), [ADR-011](ADR-011-servico-de-sessao-persistente.md) (`StaleSessionError` e ciclo de vida do serviço de sessão), [ADR-016](ADR-016-ciclo-de-vida-dos-dados.md) (comandos e `lifespan`)
  - **Interage com:** [ADR-013](ADR-013-exclusividade-de-reserva.md) (sessões diferentes executam em paralelo; a exclusividade fica no banco)
  - **Referências:** [SUMMARY §7 Contrato](../SUMMARY.md#7-contrato-da-api), [SUMMARY GT-16 a GT-18](../SUMMARY.md#10-gotchas), [PRD — DD-06](../PRD.md#pontos-de-atenção-para-os-design-documents)

## Contexto

A API precisa seguir **exatamente** o contrato do enunciado:

- caminhos, campos e códigos `201`, `200`, `404` e `409`;
- `resposta` vazia quando a execução pausa;
- eventos completos, em ordem.

O `Runner` do ADK é assíncrono (`run_async`). O framework web é livre, e o curso usa FastAPI. O ADK oferece um servidor FastAPI próprio (`adk api_server`), mas com outro contrato de rotas.

Restrições técnicas:

- o `DatabaseSessionService` levanta `StaleSessionError` em escritas concorrentes na **mesma** sessão ([ADR-011](ADR-011-servico-de-sessao-persistente.md));
- no passo 14, duas sessões diferentes são aprovadas **ao mesmo tempo**, e as duas devem responder `200`;
- erros de cota ou indisponibilidade do modelo podem ocorrer.

## Decisão

1. **FastAPI + uvicorn**, num **único processo e worker**, escutando em `localhost:8000` (`uv run aurora-api`, conforme o [ADR-016](ADR-016-ciclo-de-vida-dos-dados.md)).
2. No **`lifespan`**, são criados uma vez e compartilhados: os engines, o serviço de sessão, o `App`, o `Runner` e os serviços de domínio. Tudo é fechado no encerramento.
3. **Lock assíncrono por `session_id`:** as requisições de mensagem e de confirmação **da mesma sessão** são serializadas. Sessões diferentes executam em paralelo.
4. **Composição da resposta**, igual nas rotas de mensagens e de confirmações:
   - **`resposta`:** o texto final produzido pelos agentes na invocação corrente. Considera só eventos não parciais, ignora partes de raciocínio, e pode ser `""`.
   - **`confirmacoes_pendentes`:** calculado após a execução, conforme o [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md).
5. **Eventos:** `GET /sessoes/{id}/eventos` devolve todos os eventos em ordem, cada um serializado por completo (`model_dump(mode="json", by_alias=True, exclude_none=True)`).
6. **Mapeamento de erros:**

   | Situação | Resposta |
   | :--- | :--- |
   | Sessão inexistente | `404` em toda rota com `{session_id}` |
   | `id` de confirmação não pendente | `409`, sem chamar o `Runner` |
   | Corpo inválido | `422` |
   | Conflito de negócio (ex.: data ocupada) | Nunca é erro: vira `200` com a resposta do agente |
   | Falha do modelo (cota ou indisponibilidade) | `503` com mensagem genérica |

7. Modelos Pydantic de requisição e resposta espelham o contrato e são o único formato exposto.

## Alternativas consideradas

### A1. Servidor FastAPI do próprio ADK (`adk api_server` / `get_fast_api_app`)
- **Prós:** pronto, com sessões, execução e streaming.
- **Contras:** caminhos e formatos diferentes do contrato (`/run`, `/apps/...`); exigiria uma camada de tradução ou um proxy; menos controle sobre `404`, `409` e a composição de `confirmacoes_pendentes`.
- **Motivo do descarte:** o contrato é fixo e verificado pelo avaliador.

### A2. Múltiplos workers ou processos
- **Prós:** mais vazão.
- **Contras:** o lock por sessão deixa de valer entre processos; mais disputa de escrita no SQLite; nenhuma necessidade de vazão no escopo.
- **Motivo do descarte:** complexidade e risco sem benefício.

### A3. Outro framework (Flask, Litestar, Starlette puro)
- **Prós:** alternativas válidas.
- **Contras:** Flask não é assíncrono nativo, e o `Runner` é; os demais fogem do material do curso sem ganho específico. O FastAPI já é dependência do ADK.
- **Motivo do descarte:** o FastAPI é o caminho de menor atrito.

### A4. Sem lock por sessão (confiar no tratamento de `StaleSessionError`)
- **Prós:** menos código.
- **Contras:** requisições concorrentes na mesma sessão falhariam com erro ou exigiriam retentativa com reprocessamento do modelo.
- **Motivo do descarte:** serializar por sessão é simples e elimina a classe de erro.

## Consequências

### Positivas
- Controle total do contrato e dos códigos de status.
- Sessões diferentes concorrem livremente (passo 14), e a exclusividade fica a cargo do banco.
- Os objetos caros (engines, `Runner`) são criados uma vez.

### Negativas
- Processo único: o lock por sessão vale só dentro dele (suficiente no escopo; não escala horizontalmente sem revisão).
- A composição de `resposta` depende de interpretar os eventos da invocação (autor, parcialidade, partes de texto).

### Trade-off explícito
Abre-se mão de escala horizontal e do servidor pronto do ADK em troca de **aderência estrita ao contrato** e de um modelo de concorrência simples e previsível.
