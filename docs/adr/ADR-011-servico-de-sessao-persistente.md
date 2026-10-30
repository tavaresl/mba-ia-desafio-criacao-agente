# ADR-011 — Serviço de sessão: `DatabaseSessionService` sobre SQLite em arquivo próprio, com engine configurado para concorrência

- **Status:** Proposto (sujeito à prova de conceito de confirmação e ao teste de concorrência)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-002](ADR-002-versao-do-google-adk.md) (o extra `db` do ADK)
  - **Influencia:** [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md) (os eventos persistidos são a fonte das pendências), [ADR-009](ADR-009-identidade-do-apartamento.md) (endereçamento por `user_id`), [ADR-016](ADR-016-ciclo-de-vida-dos-dados.md) (limpeza na restauração), [ADR-017](ADR-017-api-e-modelo-de-execucao.md) (lock por sessão)
  - **Interage com:** [ADR-012](ADR-012-armazenamento-do-dominio.md) (decisão paralela para os dados do domínio)
  - **Referências:** [PRD — Disponibilidade](../PRD.md#requisitos-não-funcionais), [SUMMARY GT-06, GT-13](../SUMMARY.md#10-gotchas), [ENUNCIADO — Garantia 3](../../ENUNCIADO.md#4-garantia-3-nada-se-perde-no-reinício)

## Contexto

G3 exige que, depois de reiniciar a API, a mesma sessão continue: os eventos anteriores estão lá, as novas mensagens funcionam e as pendências continuam respondíveis.

O `InMemorySessionService` perde tudo. No ADK 2.13.0, o `DatabaseSessionService`:

- aceita uma URL assíncrona (`sqlite+aiosqlite`, `postgresql+asyncpg`) **ou** um `AsyncEngine` próprio (`db_engine=`), sem descartar um engine que não criou;
- exige o extra `google-adk[db]`;
- detecta escrita concorrente na **mesma sessão** (`StaleSessionError`).

O código do ADK **não configura** `journal_mode=WAL` nem `busy_timeout` no SQLite, conforme verificado por busca no pacote.

No passo 14, duas sessões gravam eventos ao mesmo tempo, enquanto o domínio grava reservas. A documentação de confirmação cita serviços de sessão não suportados, mas os autores do desafio observaram a confirmação funcionando com SQLite quando a resposta chega ao agente certo.

## Decisão

1. Usar **`DatabaseSessionService`** com um **`AsyncEngine` próprio** (`sqlite+aiosqlite`), num arquivo dedicado (ex.: `var/sessions.db`).
2. O engine é configurado na conexão com:
   - **`PRAGMA journal_mode=WAL`**, para leitores não bloquearem o escritor;
   - **`PRAGMA busy_timeout`** de alguns segundos, para escritas concorrentes aguardarem em vez de falhar com "database is locked".
3. O ciclo de vida do serviço (abrir e fechar o engine) é gerenciado no `lifespan` da API ([ADR-017](ADR-017-api-e-modelo-de-execucao.md)).
4. Escritas concorrentes na **mesma** sessão são evitadas pelo lock por sessão da API ([ADR-017](ADR-017-api-e-modelo-de-execucao.md)). Sessões diferentes executam em paralelo.
5. O diretório `var/` entra no `.gitignore`, e o arquivo é criado automaticamente na primeira execução.
6. O arquivo de sessões fica **separado** do banco de domínio ([ADR-012](ADR-012-armazenamento-do-dominio.md)). Isso reduz a disputa pelo lock de escrita do SQLite e permite limpar um sem tocar o outro.

## Alternativas consideradas

### A1. PostgreSQL em container (`postgresql+asyncpg`)
- **Prós:** concorrência de escrita robusta; mais próximo de produção.
- **Contras:** exige Docker na máquina do avaliador e um comando extra documentado; mais um ponto de falha no passo 1.
- **Motivo do descarte:** custo operacional desproporcional ao volume do desafio. Fica como contingência se o SQLite falhar no passo 14.

### A2. `InMemorySessionService`
- **Prós:** zero configuração.
- **Contras:** perde tudo no reinício.
- **Motivo do descarte:** viola G3.

### A3. Serviço de sessão próprio (implementação de `BaseSessionService`)
- **Prós:** controle total do esquema.
- **Contras:** reimplementa persistência de eventos, estado e detecção de concorrência; risco alto de divergir do comportamento esperado pelo `Runner`.
- **Motivo do descarte:** reinventa algo pronto e testado.

### A4. SQLite pela URL padrão, sem ajuste de engine
- **Prós:** uma linha de configuração.
- **Contras:** sem `busy_timeout`, escritas concorrentes falham com "database is locked", o que vira `500` no passo 14 (GT-06).
- **Motivo do descarte:** risco conhecido e evitável.

## Consequências

### Positivas
- Persistência completa de sessões, eventos e estado, sem infraestrutura externa.
- Reprodução trivial pelo avaliador (`uv sync` e subir a API).
- Concorrência controlada com ajustes pequenos e explícitos.

### Negativas
- O SQLite aceita um escritor por vez: sob alta concorrência, as requisições aguardam (aceitável no escopo).
- A configuração do engine é código próprio a manter, fora do padrão do ADK.

### Trade-off explícito
Aceitam-se os limites de concorrência do SQLite, mitigados por WAL, `busy_timeout` e lock por sessão, em troca de **zero infraestrutura externa** e reprodução simples.
