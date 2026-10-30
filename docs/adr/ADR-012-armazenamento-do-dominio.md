# ADR-012 — Armazenamento do domínio: SQLite em arquivo separado, acessado por SQLAlchemy async

- **Status:** Proposto
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-001](ADR-001-regras-em-camada-de-dominio.md) (os repositórios pertencem ao domínio)
  - **Influencia:** [ADR-013](ADR-013-exclusividade-de-reserva.md) (restrição única), [ADR-014](ADR-014-codigos-de-reserva.md) (registro de códigos), [ADR-016](ADR-016-ciclo-de-vida-dos-dados.md) (seed e restauração), [ADR-009](ADR-009-identidade-do-apartamento.md) (índice de sessões)
  - **Interage com:** [ADR-011](ADR-011-servico-de-sessao-persistente.md) (mesma tecnologia, arquivo separado)
  - **Referências:** [PRD — Confiabilidade e integridade de dados](../PRD.md#requisitos-não-funcionais), [SUMMARY GT-05, GT-06](../SUMMARY.md#10-gotchas), [ENUNCIADO — O ponto de partida](../../ENUNCIADO.md#o-ponto-de-partida)

## Contexto

Os arquivos de `dados/` são o estado inicial e **não podem ser alterados**. As mudanças feitas pelo assistente precisam de um armazenamento persistente que ofereça:

- **restrição de unicidade aplicada na gravação** (G5, [ADR-013](ADR-013-exclusividade-de-reserva.md));
- transações curtas e seguras sob duas aprovações simultâneas (passo 14);
- persistência entre reinícios (G3);
- consultas filtradas por apartamento, para as tools e para as rotas de verificação.

O armazenamento é de escolha livre. Um serviço externo exige um comando documentado. O ADK com o extra `db` já traz SQLAlchemy 2 (async) e `aiosqlite`.

## Decisão

1. Usar **SQLite** num arquivo próprio (ex.: `var/aurora.db`), **separado** do arquivo de sessões ([ADR-011](ADR-011-servico-de-sessao-persistente.md)).
2. Acesso via **SQLAlchemy 2 async (Core)** com `aiosqlite`, encapsulado nos repositórios do domínio ([ADR-001](ADR-001-regras-em-camada-de-dominio.md)).
3. Configurar o engine com **WAL** e **`busy_timeout`**. Escritas em transações curtas.
4. Tabelas:

   | Tabela | Conteúdo |
   | :--- | :--- |
   | `apartamentos` | Referência carregada de `dados/apartamentos.json` |
   | `areas` | Referência carregada de `dados/areas.json` (`id`, `nome`, `taxa`) |
   | `reservas` | `codigo`, `apartamento`, `area_id`, `data`, `status` (`ativa`/`cancelada`), timestamps |
   | `visitantes` | `apartamento`, `nome`, `data`, timestamps |
   | `codigos_reserva` | Registro de todos os códigos já emitidos ([ADR-014](ADR-014-codigos-de-reserva.md)) |
   | `sessoes` | Índice `session_id` → apartamento ([ADR-009](ADR-009-identidade-do-apartamento.md)) |
   | `metadados` | Marcadores de ciclo de vida, como "seed aplicado" ([ADR-016](ADR-016-ciclo-de-vida-dos-dados.md)) |

5. Chaves estrangeiras habilitadas (`PRAGMA foreign_keys=ON`) entre reservas e áreas e entre reservas, visitantes e apartamentos.
6. `dados/` é usado **somente como fonte de leitura** do seed e da restauração.

## Alternativas consideradas

### A1. Mesmo arquivo SQLite das sessões do ADK
- **Prós:** um arquivo só; possivelmente um engine só.
- **Contras:** mais disputa pelo lock de escrita único do SQLite (eventos e reservas competem); o esquema do domínio fica misturado ao esquema interno do ADK; a restauração do domínio fica acoplada às tabelas do ADK.
- **Motivo do descarte:** separar reduz a disputa e o acoplamento sem custo relevante.

### A2. Arquivos JSON em `var/`, com lock de arquivo
- **Prós:** formato idêntico ao de `dados/`; nenhuma dependência.
- **Contras:** sem restrições atômicas; exige reimplementar locking, atomicidade e consistência; a exclusividade "no instante da gravação" vira código próprio frágil.
- **Motivo do descarte:** não oferece a garantia exigida por G5.

### A3. PostgreSQL em container
- **Prós:** concorrência e índices parciais maduros.
- **Contras:** dependência de Docker e comando extra para o avaliador; mais pontos de falha no passo 1.
- **Motivo do descarte:** custo operacional desproporcional. Fica como contingência junto com o [ADR-011](ADR-011-servico-de-sessao-persistente.md).

### A4. `sqlite3` da biblioteca padrão, síncrono
- **Prós:** nenhuma dependência extra.
- **Contras:** bloqueia o event loop da API assíncrona ou exige gerenciar threads; mistura dois estilos de acesso no mesmo projeto.
- **Motivo do descarte:** o SQLAlchemy async já é dependência transitiva e mantém o código assíncrono.

## Consequências

### Positivas
- Restrições de integridade (unicidade, chaves estrangeiras) aplicadas pelo próprio banco.
- Nenhuma infraestrutura externa.
- Os mesmos repositórios servem às tools e às rotas de verificação.

### Negativas
- Dois arquivos SQLite para gerenciar (domínio e sessões).
- Os limites de escrita concorrente do SQLite valem também aqui (mitigados por WAL, `busy_timeout` e transações curtas).
- O SQLAlchemy adiciona uma camada de abstração a aprender e configurar.

### Trade-off explícito
Escolhe-se um banco embarcado com restrições reais de integridade, aceitando os limites de concorrência do SQLite, em vez de infraestrutura externa ou da fragilidade de arquivos JSON.
