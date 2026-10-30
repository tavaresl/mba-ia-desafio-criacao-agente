# ADR-001 — Regras críticas numa camada de domínio determinística, com tools como adaptadores finos

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Influencia:** [ADR-005](ADR-005-mecanismo-de-confirmacao.md) (o predicado de confirmação consulta o domínio), [ADR-009](ADR-009-identidade-do-apartamento.md) (a identidade é aplicada nas consultas do domínio), [ADR-010](ADR-010-minimizacao-de-dados-nas-tools.md) (formato das saídas), [ADR-012](ADR-012-armazenamento-do-dominio.md) (repositórios), [ADR-013](ADR-013-exclusividade-de-reserva.md), [ADR-015](ADR-015-consulta-ao-regulamento.md), [ADR-017](ADR-017-api-e-modelo-de-execucao.md) (rotas de verificação)
  - **Referências:** [PRD — Problemas priorizados](../PRD.md#problemas-priorizados), [PRD — Arquitetura e abordagem](../PRD.md#arquitetura-e-abordagem), [SUMMARY §9 Guardrails](../SUMMARY.md#9-guardrails-e-restrições)

## Contexto

A condição central do produto é que **o assistente não possa ser convencido a quebrar regra**. As regras RN-01 a RN-05 e as garantias G1, G2 e G5 precisam valer seja qual for o texto que o morador envie. Se uma regra depende só da instrução do agente, uma mensagem bem escrita a derruba.

Componentes envolvidos:

- **Agentes ADK:** decidem *o caminho* da conversa.
- **Tools:** a única porta de leitura e escrita de reservas e visitantes, uma exigência do enunciado.
- **Rotas de verificação da API:** leem os dados sem passar pelo modelo.
- **Armazenamento.**

Forças em jogo:

- O avaliador inspeciona o código (passo 15), e o README precisa apontar **o arquivo e o trecho** de cada garantia.
- As regras precisam ser testáveis sem chamar o modelo.
- As rotas de verificação e as tools precisam enxergar exatamente os mesmos dados.

## Decisão

1. Criar um **módulo de domínio puro**, com serviços de reservas, visitantes e regulamento e os repositórios correspondentes. Ele **não depende do ADK nem do modelo** e concentra:
   - todas as regras de negócio (RN-01 a RN-05);
   - a filtragem por apartamento;
   - a política de quais ações geram cobrança ou liberam acesso.
2. **Tools ADK são adaptadores finos.** Cada uma:
   - obtém a identidade do contexto da sessão ([ADR-009](ADR-009-identidade-do-apartamento.md));
   - normaliza os argumentos (ex.: "salão de festas" → `salao-de-festas`) com funções do próprio domínio;
   - chama o serviço;
   - converte o resultado para a saída mínima definida em [ADR-010](ADR-010-minimizacao-de-dados-nas-tools.md).
3. As **rotas de verificação** usam os mesmos repositórios do domínio, sem nenhum agente no caminho.
4. **Instruções de agente nunca são a única barreira de uma regra.** Elas orientam o tom e a delegação; toda regra crítica tem um ponto de código citável no README.
5. **Limites explícitos:** o domínio não conhece LLM nem ADK, e os agentes não acessam o banco diretamente.

## Alternativas consideradas

### A1. Regras nas instruções dos agentes, com tools CRUD genéricas
- **Prós:** implementação mais curta; o modelo tem flexibilidade total.
- **Contras:** é exatamente o cenário que o enunciado quer evitar; prompt injection derruba a regra; nada é verificável no código.
- **Motivo do descarte:** viola o princípio do produto e os critérios CA-14 a CA-18 e CA-26.

### A2. Regras implementadas dentro das próprias funções de tool, sem camada de domínio
- **Prós:** menos arquivos; a regra fica junto da tool.
- **Contras:** acopla as regras ao ciclo de vida e aos tipos do ADK; dificulta testar sem o runtime; as rotas de verificação precisariam duplicar consultas; o README passa a apontar código misturado com detalhes de framework.
- **Motivo do descarte:** perde reuso e testabilidade sem ganho relevante.

### A3. Guardrails centralizados em callbacks do ADK (`before_tool_callback` / `after_tool_callback`)
- **Prós:** intercepta todas as chamadas de tool num só lugar.
- **Contras:** a lógica fica separada da operação que protege; depende da ordem de execução do framework; é mais difícil de explicar e citar como "o trecho que garante X"; não atende as rotas de verificação.
- **Motivo do descarte:** fica como complemento possível, não como mecanismo principal.

## Consequências

### Positivas
- As garantias passam a ser **propriedades do código**, inspecionáveis e testáveis sem modelo.
- As rotas de verificação e as tools compartilham a mesma fonte de verdade.
- A seção Garantias do README aponta para trechos curtos e estáveis.
- Facilita a troca de topologia de agentes ([ADR-003](ADR-003-topologia-de-agentes.md)) sem mexer nas regras.

### Negativas
- Há mais uma camada a manter (serviços e repositórios), além das tools.
- Exige disciplina para que nenhuma regra "vaze" para instruções de agente como única proteção.

### Trade-off explícito
Abre-se mão de parte da flexibilidade do modelo e de alguma simplicidade inicial em troca de **regras que não dependem do que o modelo decide** e que podem ser provadas no código.
