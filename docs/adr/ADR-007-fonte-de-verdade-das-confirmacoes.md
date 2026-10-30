# ADR-007 — Pendências de confirmação e regra do `409` derivadas dos eventos persistidos da sessão

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-005](ADR-005-mecanismo-de-confirmacao.md) (formato do evento `adk_request_confirmation`), [ADR-006](ADR-006-retomada-sem-resumability.md), [ADR-011](ADR-011-servico-de-sessao-persistente.md) (eventos persistidos)
  - **Influencia:** [ADR-008](ADR-008-mensagens-com-confirmacao-pendente.md), [ADR-017](ADR-017-api-e-modelo-de-execucao.md) (composição da resposta e mapeamento de erros)
  - **Referências:** [PRD — RF-009](../PRD.md#rf-009-responder-confirmação-pendente), [SUMMARY GT-07](../SUMMARY.md#10-gotchas), [SUMMARY §7 Contrato](../SUMMARY.md#7-contrato-da-api)

## Contexto

O contrato exige três coisas:

- toda resposta de conversa lista **todas** as `confirmacoes_pendentes` da sessão, cada uma com `id`, `acao` e `detalhes`;
- a rota de confirmações responde **`409`** para qualquer `id` que não esteja pendente **naquela sessão** (inexistente, já respondido ou de outra sessão), sem executar nada;
- as pendências **sobrevivem ao reinício** (G3).

O ADK grava na sessão:

- a chamada `adk_request_confirmation`, com um id próprio e os argumentos `originalFunctionCall` e `toolConfirmation`;
- mais tarde, o `FunctionResponse` com o mesmo id.

Esses eventos já estão no armazenamento persistente de sessões.

## Decisão

1. **Uma pendência é** uma chamada `adk_request_confirmation` presente nos eventos da sessão **sem** `FunctionResponse` posterior com o mesmo id.
2. O **`id` exposto na API** é o id dessa chamada de confirmação, gerado pelo ADK e único.
3. Campos da pendência:
   - **`acao`:** derivado de `originalFunctionCall.name`, com nomes estáveis (ex.: `reservar_area`, `autorizar_visitante`);
   - **`detalhes`:** derivado de `originalFunctionCall.args` (`area` e `data`; `nome` e `data`). Pode ser enriquecido pelo domínio com dados públicos (nome da área, taxa), nunca com dados de outro apartamento ([ADR-010](ADR-010-minimizacao-de-dados-nas-tools.md)).
4. Fluxo da rota de confirmações:
   1. carregar a sessão (`404` se não existir);
   2. calcular as pendências;
   3. se o `id` não estiver entre elas, responder **`409` sem chamar o `Runner`**;
   4. caso contrário, enviar o `FunctionResponse` ([ADR-005](ADR-005-mecanismo-de-confirmacao.md)).
5. As pendências são recalculadas **depois** de cada execução, para montar a resposta (mesmo formato nas rotas de mensagens e de confirmações).
6. A checagem e o envio para a mesma sessão são serializados pelo lock por sessão definido no [ADR-017](ADR-017-api-e-modelo-de-execucao.md). Respostas simultâneas para o mesmo `id` estão fora de escopo, mas ficam cobertas por esse lock.

## Alternativas consideradas

### A1. Tabela própria de confirmações (`id`, sessão, status)
- **Prós:** status explícito; consulta direta; permite metadados (expiração, auditoria).
- **Contras:** é uma **segunda fonte de verdade**, que precisa ficar sincronizada com os eventos do ADK; pode divergir (a tabela diz "pendente" enquanto o ADK já recebeu a resposta, ou o contrário); exige gravar no momento exato em que o ADK emite o pedido (callback ou varredura de eventos).
- **Motivo do descarte:** a divergência entre as duas fontes é justamente o tipo de falha silenciosa que o enunciado alerta.

### A2. Estado em memória do processo
- **Prós:** trivial de implementar.
- **Contras:** perde as pendências no reinício (viola G3).
- **Motivo do descarte:** não atende o requisito.

## Consequências

### Positivas
- **Uma única fonte de verdade**, já persistida, que sobrevive ao reinício sem esforço adicional.
- O `409` para um `id` já respondido sai naturalmente: o `FunctionResponse` gravado retira o `id` do conjunto de pendências.
- Um `id` de outra sessão nunca aparece no conjunto da sessão consultada.

### Negativas
- Varredura linear dos eventos a cada requisição (desprezível no volume do desafio).
- Acoplamento ao formato interno do evento de confirmação do ADK (nome `adk_request_confirmation`, chaves em camelCase), mitigado pela versão fixada ([ADR-002](ADR-002-versao-do-google-adk.md)).
- Se a invocação falhar entre gravar a resposta e executar a tool, o `id` passa a contar como respondido sem efeito ([ADR-006](ADR-006-retomada-sem-resumability.md)).

### Trade-off explícito
Aceita-se depender do formato dos eventos do ADK em troca de **nunca ter duas fontes de verdade** sobre o que está pendente.
