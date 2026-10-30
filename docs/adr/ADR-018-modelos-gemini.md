# ADR-018 — Modelos Gemini: um único modelo estável da família Flash, configurável por variável de ambiente

- **Status:** Aceito (identificador definido: `gemini-3.8-flash`; validado em 2026-10-30)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-003](ADR-003-topologia-de-agentes.md) e [ADR-004](ADR-004-controle-de-turno-e-transferencias.md) (número de agentes e de chamadas por turno), [ADR-015](ADR-015-consulta-ao-regulamento.md) (tamanho do contexto na consulta)
  - **Referências:** [ENUNCIADO — Tecnologias obrigatórias](../../ENUNCIADO.md#tecnologias-obrigatórias-e-restrições), [SUMMARY GT-15](../SUMMARY.md#10-gotchas), [PRD — Riscos](../PRD.md#riscos-e-mitigação)

## Contexto

O enunciado exige **modelos Gemini com chave do Google AI Studio** e deixa a escolha do modelo livre, lembrando que modelos e limites mudam com frequência. O fluxo do avaliador faz **algumas dezenas** de chamadas ao modelo, com duas execuções simultâneas no passo 14.

A topologia escolhida chama o modelo várias vezes por turno: o `concierge` a cada turno ([ADR-004](ADR-004-controle-de-turno-e-transferencias.md)), o especialista e, nas dúvidas, o especialista de regulamento.

Forças em jogo:

- **cotas** por minuto e por dia do projeto no AI Studio;
- **qualidade** em roteamento, escolha de tool e preenchimento de argumentos;
- **estabilidade**: modelos *preview* podem mudar de comportamento ou ser descontinuados;
- **reprodutibilidade** na máquina do avaliador, que usa a própria chave.

## Decisão

1. Usar **um único modelo para todos os agentes**, com identificador lido da variável **`AURORA_MODELO`**.
   - O **valor padrão fica no código**: o `.env.example` lista apenas os nomes das variáveis, como o enunciado exige.
   - O padrão é o modelo **estável (não *preview*) mais recente da família Flash** disponível no AI Studio no momento da implementação. O identificador escolhido e o motivo ficam registrados no README.
2. Antes de fixar o padrão, conferir no AI Studio os **limites ativos** do projeto para esse modelo e verificar se eles comportam o roteiro completo, inclusive as duas chamadas simultâneas.
3. **Temperatura baixa** nos especialistas, para estabilizar a escolha de tools e os argumentos.
4. **Retentativas limitadas com espera crescente** para erros transitórios do modelo (429 e 503). Esgotadas as tentativas, a API responde `503` ([ADR-017](ADR-017-api-e-modelo-de-execucao.md)).
5. Variáveis previstas no `.env.example`: `GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI` (com o valor `FALSE` documentado no README) e `AURORA_MODELO`.
6. **Evolução prevista, não implementada agora:** uma variável opcional por agente (ex.: `AURORA_MODELO_CONCIERGE`) caso as cotas exijam um modelo mais leve no roteamento.

## Alternativas consideradas

### A1. Modelo da família Pro para todos os agentes
- **Prós:** melhor raciocínio e aderência às instruções.
- **Contras:** cotas menores no AI Studio; maior latência por turno, multiplicada pelas várias chamadas por turno.
- **Motivo do descarte:** a parte crítica (regras) está em código; o modelo só precisa rotear e preencher argumentos.

### A2. Modelos diferentes por agente (ex.: Flash-Lite no `concierge`, Flash nos especialistas)
- **Prós:** otimiza cota e custo onde a tarefa é simples (roteamento).
- **Contras:** mais configuração; um modelo menor pode errar o roteamento e piorar a experiência; mais combinações para validar.
- **Motivo do descarte:** fica como evolução prevista (item 6), ativada só se as cotas exigirem.

### A3. Identificador de modelo fixo no código, sem variável
- **Prós:** menos configuração.
- **Contras:** se o modelo for descontinuado ou a cota do avaliador for diferente, é preciso alterar o código.
- **Motivo do descarte:** os modelos mudam com frequência, como avisa o enunciado.

### A4. Modelo *preview* mais recente
- **Prós:** capacidades mais novas.
- **Contras:** comportamento e disponibilidade instáveis; costuma ter cotas mais restritas.
- **Motivo do descarte:** a estabilidade importa mais que capacidade marginal.

## Consequências

### Positivas
- Configuração simples, com uma variável para trocar o modelo sem mexer no código.
- Comportamento homogêneo entre os agentes, mais fácil de depurar.
- Resiliência a erros transitórios de cota.

### Negativas
- O mesmo modelo serve tarefas de complexidade diferente (roteamento e consulta), sem otimizar custo por agente.
- O identificador exato fica em aberto até a implementação e precisa ser revalidado se o AI Studio mudar.

### Trade-off explícito
Prefere-se simplicidade e estabilidade (um único modelo Flash estável) à otimização fina de custo e qualidade por agente, sabendo que as regras críticas não dependem da capacidade do modelo.
