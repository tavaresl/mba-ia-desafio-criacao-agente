# ADR-009 — Identidade do apartamento: `user_id` do ADK fixado na criação da sessão e lido pelas tools via contexto

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-001](ADR-001-regras-em-camada-de-dominio.md) (as consultas do domínio recebem o apartamento como parâmetro obrigatório), [ADR-011](ADR-011-servico-de-sessao-persistente.md) (endereçamento de sessões do ADK)
  - **Influencia:** [ADR-010](ADR-010-minimizacao-de-dados-nas-tools.md), [ADR-012](ADR-012-armazenamento-do-dominio.md) (tabela-índice de sessões), [ADR-016](ADR-016-ciclo-de-vida-dos-dados.md) (a restauração limpa o índice), [ADR-017](ADR-017-api-e-modelo-de-execucao.md) (resolução `session_id` → sessão e `404`)
  - **Referências:** [PRD — RF-001](../PRD.md#rf-001-iniciar-atendimento-vinculado-a-um-apartamento), [SUMMARY GT-03, GT-08](../SUMMARY.md#10-gotchas), [ENUNCIADO — Garantia 2](../../ENUNCIADO.md#3-garantia-2-cada-sessão-pertence-a-um-apartamento)

## Contexto

G2 exige três coisas:

- o apartamento é definido **uma única vez, na criação da sessão**;
- as tools usam o apartamento **da sessão**, nunca um valor escolhido pelo modelo sem validação;
- nada do que o morador escreva ("sou do 302") muda isso.

O avaliador inspeciona o código para confirmar (passo 15).

No ADK 2.13.0, uma sessão é endereçada por `(app_name, user_id, session_id)`:

- o **`user_id` é imutável** durante a vida da sessão e fica disponível às tools via `tool_context.user_id` (`ReadonlyContext.user_id`);
- o **`state`** da sessão é mutável: qualquer `state_delta` emitido por tools, callbacks ou agentes o altera;
- o `AgentTool` **repassa à sessão principal os `state_delta`** do agente aninhado (verificado em `tools/agent_tool.py`).

As rotas da API recebem **apenas `session_id`**, mas o `get_session` do ADK exige também o `user_id`.

## Decisão

1. Na criação da sessão, o **`user_id` do ADK recebe o número do apartamento**. Essa é a **única fonte de identidade** usada pelas tools, lida via `tool_context.user_id`.
2. **Nenhuma tool aceita apartamento como parâmetro**, nem opcional. Tools que recebem um código de reserva (ex.: cancelar por código) passam o apartamento da sessão ao domínio, que filtra com `WHERE apartamento = :apartamento`.
3. O apartamento **não é duplicado no `state`**. Assim, não existe uma segunda cópia mutável que possa ser usada por engano.
4. Um **índice persistente de sessões** (`session_id` → apartamento, no armazenamento do domínio, conforme o [ADR-012](ADR-012-armazenamento-do-dominio.md)) é gravado na criação. A API o usa para obter o `user_id` antes de chamar o `SessionService`; se o índice não tiver a sessão, a resposta é `404`.
5. Ordem de criação:
   1. validar o apartamento contra os apartamentos de referência;
   2. criar a sessão no ADK;
   3. gravar o índice. Se a gravação do índice falhar, a sessão do ADK é removida.
6. Apartamento inexistente na criação é rejeitado com `422` (o comportamento é livre pelo enunciado; opta-se pela recusa por segurança).

## Alternativas consideradas

### A1. `user_id` fixo para todas as sessões, com o apartamento no `state`
- **Prós:** resolver a sessão só pelo `session_id` é trivial, sem tabela-índice.
- **Contras:** o `state` é mutável por qualquer `state_delta`, inclusive repassado de um `AgentTool`, então uma falha em qualquer tool ou callback poderia sobrescrever a identidade; perde-se a partição natural de sessões por usuário no ADK.
- **Motivo do descarte:** identidade numa estrutura mutável é uma barreira mais fraca que a imutabilidade do `user_id`.

### A2. Apartamento como parâmetro das tools, validado contra o da sessão
- **Prós:** explícito na assinatura da tool.
- **Contras:** dá ao modelo a alavanca de escolher o apartamento; a validação precisa estar em todas as tools, e um esquecimento abre brecha; o próprio enunciado destaca esse padrão como ponto de inspeção.
- **Motivo do descarte:** mais superfície de erro sem benefício.

### A3. Resolver `session_id` → `user_id` com `list_sessions(app_name, user_id=None)`
- **Prós:** dispensa a tabela-índice.
- **Contras:** varre todas as sessões a cada requisição e depende da semântica de listagem do serviço.
- **Motivo do descarte:** fica como contingência caso o índice traga problemas de sincronização.

## Consequências

### Positivas
- A identidade fica numa propriedade **imutável** da sessão, que nenhum texto, tool ou estado altera.
- As tools não têm, por construção, como agir em outro apartamento.
- O trecho a citar no README é curto: o `user_id` atribuído na criação e as tools lendo `tool_context.user_id`.

### Negativas
- Um registro extra (o índice de sessões) precisa ser mantido consistente com o serviço de sessão, inclusive na restauração ([ADR-016](ADR-016-ciclo-de-vida-dos-dados.md)).
- Os agentes não "sabem" o número do apartamento nas instruções. Se for útil para a conversa, ele precisa vir de uma tool de perfil, só de leitura.

### Trade-off explícito
Aceita-se manter um índice auxiliar de sessões em troca de ancorar a identidade num **campo imutável** do ADK, em vez de num estado que qualquer componente pode alterar.
