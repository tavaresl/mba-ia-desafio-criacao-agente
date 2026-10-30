# ADR-013 — Exclusividade de reserva garantida por índice único parcial, com o conflito traduzido em resposta de negócio

- **Status:** Proposto
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-012](ADR-012-armazenamento-do-dominio.md) (SQLite com suporte a índices parciais), [ADR-001](ADR-001-regras-em-camada-de-dominio.md)
  - **Influencia:** [ADR-010](ADR-010-minimizacao-de-dados-nas-tools.md) (formato da recusa), [ADR-014](ADR-014-codigos-de-reserva.md) (cancelamento lógico mantém o histórico)
  - **Interage com:** [ADR-005](ADR-005-mecanismo-de-confirmacao.md) e [ADR-008](ADR-008-mensagens-com-confirmacao-pendente.md) (o conflito pode surgir depois da aprovação)
  - **Referências:** [ENUNCIADO — Garantia 5](../../ENUNCIADO.md#6-garantia-5-dois-moradores-uma-reserva), [SUMMARY GT-05, GT-11](../SUMMARY.md#10-gotchas), [PRD — RF-005](../PRD.md#rf-005-reservar-área-com-taxa-com-confirmação)

## Contexto

RN-01 diz que cada área aceita no máximo **uma reserva ativa por data**. G5 exige que a regra valha **no instante da gravação**: duas aprovações simultâneas (passo 14) resultam em **exatamente uma** reserva, e **as duas requisições respondem `200`**.

Conferir a agenda antes de gravar não basta, porque a outra reserva pode entrar entre a checagem e a gravação. No passo 15, o avaliador inspeciona o código em busca dessa garantia no armazenamento.

As reservas canceladas continuam existindo, para preservar o histórico e a unicidade de códigos ([ADR-014](ADR-014-codigos-de-reserva.md)). Por isso, a restrição precisa considerar **apenas as reservas ativas**.

## Decisão

1. Criar um **índice único parcial**:
   `CREATE UNIQUE INDEX ux_reserva_ativa ON reservas(area_id, data) WHERE status = 'ativa'`.
2. A reserva é gravada com um `INSERT` dentro de uma transação. A **violação desse índice** (`IntegrityError`) é capturada no repositório e convertida no resultado de domínio `Indisponivel`, que **não é exceção de sistema**.
3. A tool converte `Indisponivel` em `{"status": "indisponivel", ...}` ([ADR-010](ADR-010-minimizacao-de-dados-nas-tools.md)). O agente responde normalmente, e a API devolve `200`.
4. Uma consulta de disponibilidade antes de reservar é mantida **apenas para a experiência do morador**. Ela não é a garantia.
5. **Cancelamento é lógico** (`UPDATE ... SET status = 'cancelada'`), e libera a data sem apagar o histórico.
6. O teste de concorrência (duas aprovações disparadas em paralelo) faz parte da validação obrigatória.

## Alternativas consideradas

### A1. Checar e depois inserir na aplicação
- **Prós:** simples de escrever.
- **Contras:** condição de corrida clássica entre a checagem e a gravação.
- **Motivo do descarte:** é o exemplo que o enunciado aponta como insuficiente.

### A2. Lock em memória do processo (`asyncio.Lock` global para reservas)
- **Prós:** funciona com um único processo.
- **Contras:** a garantia fica no processo, não no armazenamento; quebra com mais de um worker ou processo; não atende a inspeção "exclusividade no instante da gravação".
- **Motivo do descarte:** garantia no lugar errado.

### A3. Tabela de "slots" `(area_id, data)` com chave primária, apagada no cancelamento
- **Prós:** funciona em bancos sem índice parcial.
- **Contras:** duas tabelas para manter sincronizadas (reserva e slot) na mesma transação; mais pontos de inconsistência.
- **Motivo do descarte:** o SQLite suporta índice parcial, e uma estrutura só é mais simples.

### A4. Transação `BEGIN IMMEDIATE` (ou serializável) com checagem dentro dela
- **Prós:** no SQLite, serializa os escritores e torna a checagem segura.
- **Contras:** a correção depende do nível de isolamento e do comportamento específico do banco; fica menos explícito no código que uma restrição declarada.
- **Motivo do descarte:** a restrição declarativa comunica a regra no próprio esquema e vale para qualquer caminho de escrita.

## Consequências

### Positivas
- A regra fica **declarada no esquema**: nenhum caminho de código, inclusive bugs futuros, consegue gravar duas reservas ativas para a mesma área e data.
- O conflito vira uma resposta de negócio, então nunca gera `500`.
- O trecho a citar no README é uma única linha DDL mais o tratamento do conflito.

### Negativas
- O conflito pode ser descoberto **depois** da aprovação. O morador que perdeu a disputa aprovou e recebe uma recusa, o que pede uma mensagem clara.
- A tradução de `IntegrityError` precisa distinguir esse índice de outras violações, que continuam sendo erros reais.

### Trade-off explícito
Aceita-se descobrir o conflito só na gravação, eventualmente depois da aprovação do morador, em troca de uma garantia **absoluta e declarativa** no armazenamento.
