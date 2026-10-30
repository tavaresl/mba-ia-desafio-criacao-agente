# ADR-008 — Nova mensagem com confirmação pendente: processar normalmente e manter a pendência válida

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-004](ADR-004-controle-de-turno-e-transferencias.md) (a nova mensagem vai ao `concierge`), [ADR-005](ADR-005-mecanismo-de-confirmacao.md), [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md) (pendências derivadas dos eventos)
  - **Influencia:** [ADR-013](ADR-013-exclusividade-de-reserva.md) (pendências antigas podem ser aprovadas depois que a data foi ocupada)
  - **Referências:** [ENUNCIADO — Fora de escopo](../../ENUNCIADO.md#fora-de-escopo), [SUMMARY D-14](../SUMMARY.md#14-decisões-em-aberto-para-o-plano)

## Contexto

O enunciado deixa livre o comportamento de uma **nova mensagem enviada enquanto há confirmação pendente**, desde que **nada execute sem confirmação**. O avaliador também pode "responder perguntas do assistente" ao longo dos fluxos, o que torna possível uma mensagem intermediária entre a criação da pendência e a aprovação.

No ADK 2.13.0, o histórico enviado ao modelo continua consistente mesmo com pendência aberta:

- a chamada original recebe uma resposta placeholder ("requires confirmation");
- os eventos `adk_request_confirmation` são filtrados do conteúdo enviado ao modelo (`flows/llm_flows/context/_contents.py`).

Assim, uma mensagem nova pode ser processada sem quebrar o pareamento entre chamadas e respostas de função.

## Decisão

1. Aceitar e **processar normalmente** novas mensagens com pendência aberta.
2. As pendências **continuam válidas e listadas** em `confirmacoes_pendentes` até serem respondidas pela rota de confirmações.
3. A aprovação de uma pendência antiga executa a ação com **revalidação total** no momento da gravação. Se a data tiver sido ocupada nesse meio-tempo, a recusa é normal ([ADR-013](ADR-013-exclusividade-de-reserva.md)).
4. As instruções orientam o agente: quando o morador disser "confirmo" na conversa, ele deve lembrar que a aprovação é feita pelo canal de confirmações, sem executar nada.
5. A prova de conceito valida que aprovar uma pendência **depois** de uma mensagem intermediária ainda chega ao especialista autor.
6. **Contingência:** se a validação falhar, adotar A2 (negar automaticamente as pendências abertas antes de processar a nova mensagem).

## Alternativas consideradas

### A1. Rejeitar a nova mensagem enquanto houver pendência
- **Prós:** estado sempre simples (no máximo uma pendência por vez).
- **Contras:** o contrato da rota de mensagens não prevê erro para esse caso; quebraria o fluxo se o avaliador responder uma pergunta do assistente com a pendência aberta.
- **Motivo do descarte:** risco de reprovar fluxos do avaliador.

### A2. Negar automaticamente as pendências abertas antes de processar a nova mensagem
- **Prós:** nunca acumula pendências antigas; o histórico fica sempre "fechado"; caminho de retomada mais simples.
- **Contras:** o morador perde a pendência sem perceber; se o avaliador mandar uma mensagem intermediária e depois aprovar, recebe `409`.
- **Motivo do descarte:** fica como **contingência**.

### A3. Ignorar a mensagem e devolver só as pendências
- **Prós:** nenhuma ambiguidade.
- **Contras:** experiência ruim; o morador não consegue fazer perguntas enquanto decide.
- **Motivo do descarte:** prejudica a conversa sem ganho de segurança.

## Consequências

### Positivas
- A conversa segue fluida: o morador pode perguntar algo antes de aprovar.
- Tolera variações do roteiro do avaliador.
- A segurança se mantém, porque nada executa sem a rota, e a gravação revalida tudo.

### Negativas
- Pendências podem se acumular na sessão, e é preciso listá-las todas a cada resposta.
- Aprovar uma pendência antiga pode resultar em recusa (data ocupada depois), o que exige uma mensagem clara.

### Trade-off explícito
Aceita-se a possibilidade de pendências acumuladas e aprovações tardias recusadas em troca de **não interromper a conversa** e de tolerar mensagens intermediárias no roteiro.
