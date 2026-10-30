# ADR-016 — Ciclo de vida dos dados: esquema idempotente na subida, seed único por marcador e restauração que também limpa as sessões

- **Status:** Proposto
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-012](ADR-012-armazenamento-do-dominio.md) (tabela `metadados`), [ADR-011](ADR-011-servico-de-sessao-persistente.md) (arquivo de sessões), [ADR-014](ADR-014-codigos-de-reserva.md) (o registro de códigos é preservado), [ADR-009](ADR-009-identidade-do-apartamento.md) (índice de sessões)
  - **Influencia:** [ADR-017](ADR-017-api-e-modelo-de-execucao.md) (comandos expostos e ações do `lifespan`)
  - **Referências:** [PRD — RF-013](../PRD.md#rf-013-restaurar-os-dados-iniciais), [SUMMARY GT-13, D-13](../SUMMARY.md#10-gotchas), passos 1 e 13 do fluxo do avaliador

## Contexto

O avaliador começa por um **clone limpo** (passo 1):

1. copia o `.env`;
2. roda `uv sync`;
3. executa os comandos do README para restaurar os dados e subir a API.

No passo 13, ele **reinicia a API sem restaurar**, e tudo precisa continuar como estava.

O comando de restauração "volta reservas e visitantes ao estado desses arquivos". Apagar ou não as sessões é decisão livre. Duas armadilhas:

- se a subida semear dados, o passo 13 quebra;
- se o seed automático depender de "tabela vazia", ele dispara por engano quando todas as reservas forem canceladas.

## Decisão

1. **Dois comandos**, expostos como scripts do projeto (`[project.scripts]`) e executados com `uv run`, portáveis e sem dependência de `make`:
   - `uv run aurora-restaurar`: restaura os dados iniciais;
   - `uv run aurora-api`: sobe a API em `localhost:8000`.
2. **Subida da API:**
   - cria o esquema se não existir (`CREATE TABLE IF NOT EXISTS`, idempotente);
   - aplica o seed inicial **somente** se o marcador `seed_aplicado` não estiver em `metadados`, ou seja, apenas no primeiro uso de um banco novo;
   - **nunca** restaura nem sobrescreve dados existentes.
3. **Restauração**, numa única transação no banco do domínio:
   1. apaga `reservas` e `visitantes`;
   2. recarrega `apartamentos` e `areas`;
   3. reinsere as reservas e os visitantes de `dados/`;
   4. **preserva** `codigos_reserva`, reinserindo os códigos iniciais de forma idempotente;
   5. grava o marcador `seed_aplicado`.
4. **A restauração também apaga todas as sessões**: as do ADK e o índice `sessoes`. Motivo: uma confirmação pendente criada antes da restauração poderia ser aprovada depois e executar sobre o estado restaurado, sem o morador ter visto esse estado.
5. A restauração deve ser executada **com a API parada**. O README documenta essa ordem (restaurar, depois subir).
6. Ambos os comandos funcionam num clone limpo e criam o diretório `var/` e os arquivos se não existirem.

## Alternativas consideradas

### A1. Seed a cada subida
- **Prós:** sempre parte de um estado conhecido.
- **Contras:** apaga as mudanças do fluxo no reinício e viola G3 (passo 13).
- **Motivo do descarte:** incompatível com o requisito.

### A2. Seed automático quando as tabelas estiverem vazias
- **Prós:** dispensa marcador.
- **Contras:** "vazio" é um estado de negócio legítimo (todas as reservas canceladas) e dispararia uma restauração indevida.
- **Motivo do descarte:** heurística frágil.

### A3. Restauração que mantém as sessões
- **Prós:** preserva o histórico de conversas.
- **Contras:** pendências antigas poderiam ser aprovadas sobre o estado restaurado; os eventos citariam reservas que deixaram de existir.
- **Motivo do descarte:** risco a G1 maior que o valor de manter o histórico.

### A4. `Makefile` ou scripts shell
- **Prós:** convenção comum.
- **Contras:** `make` não é garantido em todas as máquinas; shell difere entre sistemas.
- **Motivo do descarte:** `uv run` já é pré-requisito e funciona igual em qualquer plataforma.

## Consequências

### Positivas
- O passo 13 está protegido por construção: a subida nunca mexe em dados existentes.
- O primeiro uso funciona mesmo que alguém suba a API antes de restaurar.
- Depois de restaurar, o estado fica limpo e coerente, sem pendências que possam executar sobre dados restaurados.

### Negativas
- A restauração apaga o histórico de conversas.
- É preciso parar a API para restaurar, uma ordem de operação a documentar.
- O seed inicial e a restauração compartilham lógica e precisam ser mantidos em conjunto.

### Trade-off explícito
Sacrifica-se o histórico de conversas na restauração em troca de um estado **coerente e sem pendências obsoletas**, e se usa um marcador explícito em vez de heurísticas para decidir o seed.
