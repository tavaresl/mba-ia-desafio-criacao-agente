# ADR-010 — Minimização de dados nas saídas das tools e nos payloads de confirmação

- **Status:** Proposto
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-001](ADR-001-regras-em-camada-de-dominio.md) (os serviços devolvem resultados de domínio tipados), [ADR-009](ADR-009-identidade-do-apartamento.md) (o apartamento da sessão filtra todas as consultas)
  - **Influencia:** [ADR-007](ADR-007-fonte-de-verdade-das-confirmacoes.md) (conteúdo de `detalhes`), [ADR-013](ADR-013-exclusividade-de-reserva.md) (formato da recusa por conflito)
  - **Referências:** [PRD — RF-003, RF-006, RF-007](../PRD.md#requisitos-funcionais), [SUMMARY GT-03, GT-11, GT-16](../SUMMARY.md#10-gotchas), [SUMMARY §4 Dados iniciais](../SUMMARY.md#4-dados-iniciais-fatos-que-o-avaliador-usa)

## Contexto

G2 proíbe tanto **alterar** quanto **trazer para a conversa** dados de outro apartamento. O avaliador procura dados de controle nas respostas **e** em `GET /sessoes/{id}/eventos`, que traz o conteúdo completo de cada evento, inclusive as respostas das tools e os argumentos dos pedidos de confirmação. Os dados de controle são:

- `RSV-4821` e `Marina Duarte`, nos passos 3, 4 e 10;
- o número `302` isolado, no passo 10.

Consequência: **qualquer dado de terceiro que uma tool devolva ao modelo já reprova**, mesmo que o modelo não o repita. Instruções do tipo "não revele" não bastam. Os canais de vazamento previstos são:

- resposta de disponibilidade com o dono da reserva;
- mensagem de erro com código ou apartamento;
- exceção transformada em texto;
- tool de listagem genérica.

## Decisão

1. Toda tool devolve **apenas registros do apartamento da sessão**.
2. Formatos fixos de saída, definidos por tipos explícitos (TypedDict ou Pydantic), sem repassar linhas do banco:

   | Situação | Saída |
   | :--- | :--- |
   | Disponibilidade | `{"area": ..., "data": ..., "disponivel": true \| false}`: nunca o código nem o dono |
   | Reserva recusada por ocupação, na checagem ou na gravação | `{"status": "indisponivel", "area": ..., "data": ...}` |
   | Cancelamento de reserva que não pertence ao apartamento ou não existe | `{"status": "nao_encontrada"}`: as duas situações são **indistinguíveis** |
   | Minhas reservas e meus visitantes | apenas os registros próprios (`codigo`, `area`, `data` / `nome`, `data`) |

3. Erros vêm de um **catálogo fixo de mensagens de domínio**. Exceções, SQL ou objetos internos nunca são convertidos em texto na saída da tool.
4. **Não existe tool de leitura global.** As rotas de verificação ficam fora do alcance dos agentes.
5. Os `detalhes` das pendências contêm apenas os argumentos da própria ação, eventualmente enriquecidos com dados públicos da área (nome, taxa).
6. As instruções reforçam que o assistente não menciona números de outros apartamentos. Isso é complemento: a garantia está nos itens 1 a 4.

## Alternativas consideradas

### A1. Filtro de saída por callback (`after_tool_callback`) que remove dados de terceiros
- **Prós:** defesa em profundidade centralizada.
- **Contras:** é uma lista de bloqueio, que precisa conhecer todos os dados de terceiros e falha com formatos imprevistos; mascara saídas mal projetadas em vez de impedi-las.
- **Motivo do descarte:** fica como complemento opcional, não como mecanismo principal.

### A2. Informar o ocupante ou o código para melhorar a experiência ("ocupada pelo 302")
- **Prós:** o morador sabe com quem negociar.
- **Contras:** viola G2 diretamente.
- **Motivo do descarte:** proibido.

### A3. Confiar nas instruções para o modelo não repetir os dados
- **Prós:** nenhum código adicional.
- **Contras:** os eventos gravam a saída da tool mesmo que o modelo não a repita; prompt injection pode extrair o dado.
- **Motivo do descarte:** não atende a verificação nos eventos.

## Consequências

### Positivas
- Vazamento impossível **por construção**: o dado de terceiro nunca chega ao modelo nem ao histórico.
- As saídas tipadas documentam o contrato de cada tool e facilitam a revisão.
- É fácil verificar: basta procurar os dados de controle nos eventos.

### Negativas
- Respostas menos informativas: o morador não sabe por que uma reserva "não foi encontrada" nem quem ocupou a data.
- O catálogo de mensagens de erro precisa ser mantido.

### Trade-off explícito
Sacrifica-se informatividade da conversa em troca de **privacidade garantida por construção**, verificável inclusive no histórico completo da sessão.
