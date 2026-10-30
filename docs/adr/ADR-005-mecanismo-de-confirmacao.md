# ADR-005 — Mecanismo de confirmação: confirmação nativa do ADK com `require_confirmation` declarativo

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-001](ADR-001-regras-em-camada-de-dominio.md) (o predicado consulta a política do domínio), [ADR-002](ADR-002-versao-do-google-adk.md), [ADR-003](ADR-003-topologia-de-agentes.md) (as tools com confirmação vivem em especialistas `chat`)
  - **Influencia:** [ADR-006](ADR-006-retomada-sem-resumability.md) (como a retomada acontece), [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md) (formato do evento que vira pendência), [ADR-013](ADR-013-exclusividade-de-reserva.md) (revalidação na gravação)
  - **Referências:** [PRD — RF-005, RF-008, RF-009](../PRD.md#requisitos-funcionais), [SUMMARY GT-01, GT-09, GT-10, GT-14](../SUMMARY.md#10-gotchas)

## Contexto

A garantia G1 exige:

- ações que geram cobrança (reserva de área com `taxa > 0`) ou liberam acesso (autorização de visitante) ficam **pendentes até a rota de confirmações**;
- aprovar executa **uma única vez**, e negar não muda nada;
- ações sem cobrança ou acesso (reserva da quadra, cancelamento) **não** pedem confirmação;
- a confirmação vem do sistema, nunca do texto da conversa.

Mecanismos disponíveis no ADK 2.13.0 (verificados no código):

- **`FunctionTool(require_confirmation=bool | Callable[..., bool])`.** Antes de executar, a tool avalia o predicado. Se a confirmação for exigida e ainda não houver resposta, o ADK:
  - devolve à tool o placeholder *"This tool call requires confirmation…"*;
  - emite uma chamada `adk_request_confirmation` com `originalFunctionCall` (nome e argumentos) e `toolConfirmation`.

  Quando chega a resposta, o ADK verifica que a chamada original existe no histórico, **que a tool ainda exige confirmação para aqueles argumentos** e que nome e argumentos coincidem. Depois, reexecuta a tool com `tool_context.tool_confirmation`. Se a resposta for negativa, a tool devolve *"This tool call is rejected."* sem executar o corpo.
- **`tool_context.request_confirmation(hint, payload)`:** o mesmo fluxo, disparado de forma imperativa dentro do corpo da tool, com payload livre.
- **`RequestInput` em tools geradoras:** pausa genérica, que exige `ResumabilityConfig`.
- **Uma pendência própria, fora do ADK.**

## Decisão

1. Usar a **confirmação nativa do ADK com `require_confirmation` declarativo**:
   - **`reservar_area(area, data)`:** o predicado chama a política do domínio (`exige_confirmacao(area)`). Ele é **fail-closed**: devolve `False` **somente** quando a área se resolve para uma área conhecida com `taxa == 0`; qualquer ambiguidade exige confirmação. O predicado e o corpo usam a mesma função de normalização de área do domínio.
   - **`autorizar_visitante(nome, data)`:** `require_confirmation=True`, sempre.
   - **`cancelar_reserva`, consultas e listagens:** sem confirmação.
2. A API responde a uma confirmação enviando ao `Runner` uma mensagem `role="user"` com um único `FunctionResponse`:
   - `name="adk_request_confirmation"`;
   - `id` igual ao id da chamada de confirmação;
   - `response={"confirmed": <bool>}`.
3. O **corpo da tool revalida tudo na execução** (área, data, identidade, exclusividade na gravação conforme o [ADR-013](ADR-013-exclusividade-de-reserva.md)). A confirmação é necessária, mas não suficiente.
4. As instruções dos especialistas proíbem pedir "confirma?" no chat e orientam a avisar que a aprovação é feita pelo canal de confirmações. Frases como "já estou confirmando aqui" não têm efeito, porque só o `FunctionResponse` libera a execução.
5. Um novo pedido após uma recusa gera uma **nova** chamada de tool e, portanto, uma nova confirmação (GT-14).

## Alternativas consideradas

### A1. `tool_context.request_confirmation(hint, payload)` imperativo, dentro da tool
- **Prós:** payload rico e controlado (ex.: nome da área, taxa); permite checar a disponibilidade **antes** de pedir confirmação e responder "ocupada" sem criar pendência.
- **Contras:** a decisão de "quando pedir" fica misturada ao corpo da tool; é mais fácil errar o fluxo (esquecer de checar `tool_confirmation` na reexecução); a política fica menos visível para o avaliador.
- **Motivo do descarte:** fica como **evolução possível** se a checagem prévia de disponibilidade virar requisito de experiência. Os detalhes de `confirmacoes_pendentes` já podem ser enriquecidos pela API ([ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md)).

### A2. Pendência própria fora do ADK (a tool grava a "ação pendente" e a rota de confirmação executa no domínio)
- **Prós:** independe do roteamento do `Runner` (elimina GT-01); controle total de execução única.
- **Contras:** a ação executa fora da tool, então a chamada efetiva não aparece nos eventos; é preciso sintetizar uma mensagem ao agente para ele narrar o resultado; reimplementa algo que o ADK oferece e que é o conceito avaliado.
- **Motivo do descarte:** fica como **contingência** se a prova de conceito falhar em todas as topologias.

### A3. Confirmação pela conversa (o agente pergunta "confirma?" e o morador responde "sim")
- **Prós:** nenhuma infraestrutura.
- **Contras:** viola G1 diretamente; é forjável por texto.
- **Motivo do descarte:** proibido pelo enunciado.

### A4. `RequestInput` com tools geradoras e `ResumabilityConfig`
- **Prós:** pausa genérica e flexível.
- **Contras:** exige retomada experimental com execução *at-least-once* ([ADR-006](ADR-006-retomada-sem-resumability.md)); afasta-se do mecanismo específico de confirmação de tools.
- **Motivo do descarte:** mais risco, nenhum ganho para o caso.

## Consequências

### Positivas
- A política de confirmação fica **declarada na definição da tool** e é fácil de apontar no README.
- O próprio ADK revalida a resposta contra o histórico e contra o predicado. Isso bloqueia respostas para chamadas inexistentes ou para tools que não exigem confirmação.
- `detalhes` sai direto dos argumentos originais (`area` e `data`; `nome` e `data`).
- O ADK marca `skip_summarization`, então a `resposta` pode vir vazia na pausa, como o contrato permite.

### Negativas
- Com o predicado só pela taxa, reservar uma data já ocupada gera pendência; a recusa só aparece depois da aprovação (aceitável pelo passo 10).
- O histórico do modelo contém o placeholder "requires confirmation", e as instruções precisam evitar que o modelo o interprete como erro.
- O fluxo fica acoplado ao formato do evento `adk_request_confirmation` (mitigado pela versão fixada).

### Trade-off explícito
Prefere-se o mecanismo nativo e declarativo, que o ADK valida e que o avaliador reconhece, aceitando a dependência do roteamento do `Runner`. Essa dependência só se elimina com a contingência A2, que tem custo conceitual maior.
