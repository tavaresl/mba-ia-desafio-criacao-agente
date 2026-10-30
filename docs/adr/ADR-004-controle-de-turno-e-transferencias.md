# ADR-004 — Controle de turno: especialistas sem transferência para o pai nem para os pares

- **Status:** Proposto (sujeito à prova de conceito de confirmação)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-003](ADR-003-topologia-de-agentes.md) (os especialistas `reservas` e `visitantes` são `chat` por transferência)
  - **Influencia:** [ADR-005](ADR-005-mecanismo-de-confirmacao.md) e [ADR-008](ADR-008-mensagens-com-confirmacao-pendente.md) (para onde vão as respostas e as novas mensagens), [ADR-018](ADR-018-modelos-gemini.md) (chamadas extras por turno)
  - **Referências:** [ENUNCIADO — Dicas finais](../../ENUNCIADO.md#dicas-finais) ("bloqueios de transferência"), [SUMMARY GT-01](../SUMMARY.md#10-gotchas)

## Contexto

Com especialistas em `mode='chat'`, a função `find_agent_to_run` (ADK 2.13.0, `agents/_agent_router.py`) decide quem atende cada nova mensagem:

1. Se a última mensagem é uma **resposta de função** do usuário, ela vai ao **agente autor da chamada** correspondente. Essa regra vem antes de todas as outras.
2. Senão, a mensagem vai ao último agente que respondeu, **desde que** ele possa transferir de volta pela árvore (`is_transferable_across_agent_tree`).
3. Em último caso, ela vai ao agente principal.

Dois bloqueios afetam esse comportamento:

- `disallow_transfer_to_parent=True`: impede o especialista de devolver o controle por decisão do modelo e, pela documentação do campo, **devolve o controle ao pai no turno seguinte**.
- `disallow_transfer_to_peers=True`: impede a transferência entre especialistas.

Sem bloqueios, o dono do próximo turno depende de quem falou por último e das decisões do modelo de transferir, o que torna o roteamento difícil de prever e de explicar. O enunciado cita os bloqueios de transferência entre os fatores que mudaram o roteamento da confirmação nos testes dos autores.

## Decisão

1. Os especialistas `reservas` e `visitantes` são configurados com **`disallow_transfer_to_parent=True`** e **`disallow_transfer_to_peers=True`** (topologia estrela estrita).
2. Efeitos esperados:
   - **toda nova mensagem de texto começa no `concierge`**, que delega de novo;
   - **toda resposta de confirmação vai ao especialista autor** da chamada, pela regra 1 do roteador.
3. As instruções dos especialistas orientam a resolver o pedido dentro do próprio domínio e a encerrar a resposta. Pedidos fora do domínio ficam para o próximo turno, que recomeça no `concierge`.
4. Mensagens com várias intenções (ex.: "reserve o salão e autorize a Joana") são atendidas uma intenção por turno. O especialista informa o que fez, e o restante é retomado no turno seguinte.
5. A prova de conceito confirma três comportamentos:
   - a aprovação é respondida pelo especialista;
   - a mensagem seguinte é atendida pelo `concierge`;
   - os dois funcionam também depois de reiniciar a API.

## Alternativas consideradas

### A1. Sem bloqueios (transferência livre)
- **Prós:** continuidade natural (o especialista segue na conversa ao fazer perguntas); menos chamadas ao modelo.
- **Contras:** quem atende o turno depende do último autor e de decisões do modelo; um especialista pode ficar com perguntas fora do domínio; o comportamento é mais difícil de reproduzir e explicar.
- **Motivo do descarte:** a previsibilidade do roteamento vale mais que a economia de uma chamada por turno, dado o risco GT-01.

### A2. Bloquear só a transferência entre pares
- **Prós:** o especialista ainda pode devolver ao principal quando perceber que o pedido é de outro domínio.
- **Contras:** a devolução continua dependendo de o modelo decidir transferir; o dono do turno seguinte segue variável.
- **Motivo do descarte:** resolve só parte do problema.

### A3. Roteamento próprio por callbacks ou por um agente customizado
- **Prós:** controle total.
- **Contras:** reimplementa parte do roteador do ADK, aumentando o risco de quebrar a retomada da confirmação.
- **Motivo do descarte:** complexidade desproporcional.

## Consequências

### Positivas
- O ponto de entrada de cada turno é determinístico: o `concierge`.
- A retomada da confirmação segue a regra de maior precedência do roteador (resposta de função ao autor), que não depende dos bloqueios.
- O comportamento fica fácil de explicar no README.

### Negativas
- Uma chamada extra ao modelo por turno (o `concierge` sempre decide a delegação).
- Pedidos com várias intenções levam mais de um turno.
- Quando o especialista pergunta algo ("qual data?"), a resposta do morador passa de novo pelo `concierge` antes de voltar ao especialista.

### Trade-off explícito
Troca-se fluidez de conversa e algumas chamadas ao modelo por **um roteamento previsível**, menos exposto às variações que o enunciado aponta como a armadilha mais cara.
