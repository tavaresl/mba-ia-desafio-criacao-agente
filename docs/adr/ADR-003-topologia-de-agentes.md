# ADR-003 — Topologia de agentes: principal + especialistas `chat` por transferência + regulamento como `AgentTool`

- **Status:** Proposto (sujeito à prova de conceito de confirmação)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-002](ADR-002-versao-do-google-adk.md) (comportamentos verificados na 2.13.0)
  - **Influencia:** [ADR-004](ADR-004-controle-de-turno-e-transferencias.md) (bloqueios de transferência dos especialistas), [ADR-005](ADR-005-mecanismo-de-confirmacao.md) e [ADR-006](ADR-006-retomada-sem-resumability.md) (onde as confirmações nascem e para onde voltam), [ADR-015](ADR-015-consulta-ao-regulamento.md) (isolamento do regulamento), [ADR-018](ADR-018-modelos-gemini.md) (número de chamadas ao modelo)
  - **Referências:** [PRD — DD-01](../PRD.md#pontos-de-atenção-para-os-design-documents), [SUMMARY GT-01, GT-02](../SUMMARY.md#10-gotchas), [ENUNCIADO — Requisito 1](../../ENUNCIADO.md#1-um-assistente-vários-especialistas)

## Contexto

O enunciado exige **um agente principal e no mínimo dois especialistas**, com a forma de acionamento livre e justificada no README. Os domínios do produto são reservas, visitantes e regulamento.

No ADK 2.13.0 há quatro formas de acionar um especialista:

| Forma | Como funciona (verificado no código) | Efeito sobre as garantias |
| :--- | :--- | :--- |
| `sub_agents` em `mode='chat'` | O modelo chama `transfer_to_agent`; os eventos do especialista ficam na sessão principal | Uma confirmação pedida pelo especialista volta para ele (`find_agent_to_run` → `ROUTE_TO_AUTHOR`) |
| `sub_agents` em `mode='single_turn'`/`'task'` | Delegação exposta como tool, executada *inline* num sub-branch da sessão principal | A resposta de confirmação é roteada a quem delegou (`_resolve_task_delegator`) e reexecutada (`REPLAY_CALLS`): um caminho mais longo e sensível à versão |
| `AgentTool` | O agente roda num `Runner` próprio com `InMemorySessionService` **descartado** ao final | **Não retoma** chamadas de longa duração (o log diz "AgentTool cannot resume because its nested session is discarded"); os eventos internos **não** entram na sessão principal |
| `Workflow` (grafo) | Roteamento determinístico por nós | Outra superfície de API, fora dos conceitos do curso |

Forças em jogo:

- **G1:** a confirmação precisa voltar ao agente que a pediu, com sessão persistida e após reinício.
- **G4:** o texto do regulamento não deve entrar no histórico, e a consulta deve sair barata.
- **Passo 12:** os eventos da sessão precisam mostrar as chamadas de tool feitas na conversa.

## Decisão

1. **Agente principal `concierge`** (`LlmAgent`, `mode='chat'`):
   - entende a intenção e delega;
   - **não tem tools de dados nem o regulamento** nas instruções.
2. **Especialista `reservas`** (`sub_agents`, `mode='chat'`, acionado por transferência). Tools: listar áreas, consultar disponibilidade, listar minhas reservas, reservar área e cancelar reserva.
3. **Especialista `visitantes`** (`sub_agents`, `mode='chat'`, acionado por transferência). Tools: listar meus visitantes e autorizar visitante.
4. **Especialista `regulamento`**, exposto ao principal como **`AgentTool`**:
   - sua consulta ao regulamento ([ADR-015](ADR-015-consulta-ao-regulamento.md)) acontece na sessão aninhada descartável;
   - só a resposta final entra na sessão principal, como resposta da tool.
5. **Restrição de projeto:** tools que pedem confirmação (G1) **só podem existir em especialistas `chat`**, nunca em agentes executados por `AgentTool` ou em modo `single_turn`/`task`.
6. **Motivo de separar `reservas` e `visitantes`:**
   - as duas políticas de confirmação são diferentes (condicional à taxa ou sempre);
   - conjuntos menores de tools melhoram a escolha da tool pelo modelo;
   - a fronteira fica clara no README.
7. **Prova de conceito obrigatória antes do restante da implementação:**
   - reservar o salão, aprovar e conferir a reserva gravada, com SQLite;
   - repetir a aprovação após reiniciar a API.

## Alternativas consideradas

### A1. Todos os especialistas como `sub_agents` `chat`, inclusive o regulamento
- **Prós:** uniformidade; um único mecanismo de acionamento.
- **Contras:** o capítulo devolvido pela tool de regulamento fica gravado na sessão principal e passa a compor o histórico das chamadas seguintes, o que fere o espírito de G4 (custo) e aumenta o risco de o histórico conter texto do regulamento.
- **Motivo do descarte:** isolar o regulamento custa pouco e protege G4.

### A2. Especialistas em `mode='single_turn'` ou `'task'` (recomendado pela documentação no lugar do `AgentTool`)
- **Prós:** o agente principal mantém o controle da conversa; execução *inline* na sessão principal; caminho preferido pela documentação do ADK 2.
- **Contras:** a confirmação pedida dentro de uma delegação é roteada a quem delegou e reexecutada via sub-branch, exatamente o tipo de combinação que os autores viram falhar com sessão persistida; `single_turn` não conversa com o usuário (não pode pedir dados faltantes).
- **Motivo do descarte:** fica como **contingência** se a prova de conceito com `chat` falhar.

### A3. `AgentTool` para todos os especialistas
- **Prós:** isolamento total de contexto; o principal sempre no controle.
- **Contras:** **não retoma confirmações** (sessão aninhada descartada, verificado em `tools/agent_tool.py`); as chamadas de tool de reservas e visitantes não aparecem nos eventos da sessão (passo 12).
- **Motivo do descarte:** incompatível com G1.

### A4. Agente único com todas as tools e "especialistas" nominais
- **Prós:** menor número de chamadas ao modelo.
- **Contras:** não atende o requisito de especialistas reais (CA-05); concentra todas as tools e instruções num só contexto.
- **Motivo do descarte:** não atende o requisito.

### A5. `Workflow` (grafo de nós) do ADK 2
- **Prós:** roteamento determinístico.
- **Contras:** superfície de API diferente da vista no curso; menos natural para conversa livre; o roteamento de interrupções segue outra lógica e também precisaria ser validado.
- **Motivo do descarte:** custo de aprendizado e risco sem benefício claro para o escopo.

## Consequências

### Positivas
- O caminho da confirmação é o mais curto possível: o especialista que pede é o autor da chamada e recebe a resposta.
- As chamadas de tool de reservas e visitantes ficam visíveis nos eventos (passo 12).
- O texto do regulamento nunca entra na sessão principal (G4 com defesa em profundidade).

### Negativas
- O uso direto de `AgentTool` é **desencorajado** pela documentação da 2.13.0; o risco de mudança futura é mitigado pela versão fixada ([ADR-002](ADR-002-versao-do-google-adk.md)).
- Transferências adicionam chamadas ao modelo por turno ([ADR-018](ADR-018-modelos-gemini.md)).
- O especialista de regulamento não tem memória da conversa (cada consulta começa do zero).

### Trade-off explícito
Escolhe-se uma topologia mista (transferência para quem confirma, `AgentTool` para quem só consulta) em vez de um mecanismo uniforme. Aceita-se mais heterogeneidade em troca do caminho de confirmação mais curto e do isolamento do regulamento.
