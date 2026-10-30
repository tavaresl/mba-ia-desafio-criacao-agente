# ADR-006 — Retomada da confirmação sem `ResumabilityConfig` (App não resumível)

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-003](ADR-003-topologia-de-agentes.md) (confirmações nascem em especialistas `chat`), [ADR-005](ADR-005-mecanismo-de-confirmacao.md) (a resposta é um `FunctionResponse` enviado pelo usuário)
  - **Influencia:** [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md) (cada resposta abre uma nova invocação), [ADR-011](ADR-011-servico-de-sessao-persistente.md)
  - **Referências:** [ENUNCIADO — Dicas finais](../../ENUNCIADO.md#dicas-finais) ("a configuração de retomada do App"), [SUMMARY GT-01](../SUMMARY.md#10-gotchas)

## Contexto

O `App` do ADK aceita `resumability_config=ResumabilityConfig(is_resumable=True)`, um recurso marcado como **experimental**. Com ele, o runner pausa a invocação numa chamada de longa duração e retoma a mesma invocação depois. O próprio código da 2.13.0 (`apps/_configs.py`) avisa que a retomada é *best-effort*:

- *"Tool call to resume needs to be idempotent because we only guarantee an at-least-once behavior once resumed."*;
- *"Any temporary / in-memory state will be lost upon resumption."*

No roteador (`decide_resume_action`), uma resposta de função cujo **autor é o usuário** já resulta em `ROUTE_TO_AUTHOR`, com ou sem retomada habilitada. A resumibilidade só muda o roteamento quando a resposta não vem do usuário, ou em delegações por sub-branch (`single_turn`/`task`).

Já G1 exige que a aprovação **execute a ação exatamente uma vez**. A autorização de visitante não é naturalmente idempotente.

## Decisão

1. Construir o `App` **sem `ResumabilityConfig`** (o padrão é `is_resumable=False`). O `App` continua sendo usado, para ter `app_name` estável e um ponto único de configuração.
2. Cada resposta de confirmação **inicia uma nova invocação**. O roteador entrega a resposta ao especialista autor, que reexecuta **apenas** a chamada confirmada.
3. A prova de conceito confirma três comportamentos:
   - a aprovação executa a tool uma vez (conferido no banco);
   - o reenvio do mesmo `id` não reexecuta (409, conforme o [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md));
   - os dois valem após reiniciar a API.
4. **Gatilho de revisão:** se a topologia recuar para `single_turn`/`task` (contingência do [ADR-003](ADR-003-topologia-de-agentes.md)) e a retomada exigir resumibilidade, este ADR será substituído. A substituição precisa vir acompanhada de chaves de idempotência para as escritas.

## Alternativas consideradas

### A1. `App` com `ResumabilityConfig(is_resumable=True)`
- **Prós:** suporte oficial a pausar e retomar; necessário em algumas topologias de delegação; permite retomar invocações que falharam no meio.
- **Contras:** é experimental; a garantia *at-least-once* abre espaço para **execução duplicada**, a menos que toda escrita seja idempotente (para visitantes seria preciso uma chave de idempotência por confirmação); mais estado persistido por invocação; é um dos fatores que os autores viram mudar o roteamento.
- **Motivo do descarte:** não é necessário para a topologia escolhida e aumenta o risco de violar "exatamente uma vez".

### A2. Evitar o `App` e usar o `Runner` direto com o agente raiz
- **Prós:** uma camada a menos.
- **Contras:** perde o ponto central de configuração (plugins, compactação e retomada futura) e o `app_name` coerente com o serviço de sessão.
- **Motivo do descarte:** o custo do `App` é desprezível.

## Consequências

### Positivas
- Semântica simples: uma resposta gera uma invocação, que gera no máximo uma execução da tool confirmada.
- Não depende de um recurso experimental.
- A execução única não depende de idempotência implícita das escritas.

### Negativas
- Uma invocação interrompida por falha (ex.: erro de cota do modelo) não é retomada automaticamente. Se a falha ocorrer depois de a resposta ser gravada e antes de a tool executar, a pendência fica respondida sem efeito, e o morador precisa pedir de novo.
- Se a topologia mudar, esta decisão precisa ser revista.

### Trade-off explícito
Abre-se mão da retomada automática de invocações interrompidas em troca de **garantir a execução única** da ação confirmada sem depender de um recurso experimental.
