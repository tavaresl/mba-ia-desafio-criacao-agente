# Assistente virtual do Residencial Aurora

Assistente em **Google ADK 2.13.0** (Gemini) exposto por uma API FastAPI em `http://localhost:8000`. O morador reserva
o salão de festas, a churrasqueira e a quadra, cancela as próprias reservas, autoriza visitantes e tira dúvidas sobre o
regulamento. **O modelo conduz a conversa; o código decide o que é permitido**: as cinco garantias abaixo valem
qualquer que seja a mensagem do morador.

- Enunciado do desafio: [`ENUNCIADO.md`](ENUNCIADO.md) · Decisões de arquitetura: [`docs/adr/`](docs/adr/README.md) ·
  Design das features: [`docs/fdd/`](docs/fdd/README.md)

---

## Arquitetura

### Camadas

```text
aurora.api          rotas HTTP finas + montagem (único módulo que conhece todas as implementações)
aurora.conversa     Runner, sessões persistentes, pendências e confirmações
aurora.agentes      concierge, especialistas, tools (adaptadores finos) e App do ADK
aurora.regulamento  índice por capítulo + especialista isolado
aurora.dominio      regras de negócio determinísticas (sem ADK, sem modelo)
aurora.persistencia SQLite (única dona do SQL do domínio)
aurora.contratos    Protocols, DTOs e tipos de resultado (só biblioteca padrão)
```

As tools **não têm regra de negócio**: repassam a chamada ao serviço de domínio e convertem o resultado tipado num
`dict` mínimo ([ADR-001](docs/adr/ADR-001-regras-em-camada-de-dominio.md)).

### Agentes

| Agente | Responsabilidade | Como é acionado | Por quê |
| :--- | :--- | :--- | :--- |
| `concierge` (principal) | Classifica o pedido e delega; não executa ações e **não tem o regulamento** nas instruções | Raiz do `App`; todo turno começa nele | Mantém o contexto pequeno e a decisão de roteamento num único lugar |
| `reservas` | Reservar, cancelar, listar reservas, consultar disponibilidade (livre/ocupada) e áreas | Transferência (`transfer_to_agent`), `mode="chat"`, sem transferência para o pai nem para os pares | Precisa conversar (pedir área e data) e ser quem recebe a resposta de confirmação |
| `visitantes` | Autorizar e listar visitantes | Igual ao `reservas` | Mesmo motivo; ação que libera acesso, sempre com confirmação |
| `regulamento` | Responde dúvidas consultando **um capítulo** por vez | `AgentTool` do `concierge` | A sessão aninhada do `AgentTool` é descartada: o texto do capítulo nunca entra nos eventos da sessão principal, só a resposta curta ([ADR-015](docs/adr/ADR-015-consulta-ao-regulamento.md)) |

- Os especialistas não transferem de volta: o turno seguinte recomeça no `concierge`, e a resposta de confirmação é
  entregue pelo `Runner` ao agente autor da chamada ([ADR-004](docs/adr/ADR-004-controle-de-turno-e-transferencias.md),
  [ADR-006](docs/adr/ADR-006-retomada-sem-resumability.md)). O `App` não usa `ResumabilityConfig`.
- Por que `reservas` e `visitantes` são transferência e `regulamento` é `AgentTool`: confirmação só retoma bem quando
  quem pediu a confirmação está na sessão principal; já o regulamento nunca pede confirmação e precisa do isolamento
  ([ADR-003](docs/adr/ADR-003-topologia-de-agentes.md)).
- **Modelo:** `gemini-3.8-flash` para todos os agentes (Flash estável mais recente na página de deprecações do AI
  Studio no momento da implementação; os modelos 2.5 estão restritos a quem já os usava), com temperatura 0,1 e
  retentativas com espera crescente. Troque com `AURORA_MODELO` ([ADR-018](docs/adr/ADR-018-modelos-gemini.md)).

### Armazenamento

Dois arquivos SQLite em `var/` (ignorado pelo Git), ambos com WAL, `busy_timeout` e transações `BEGIN IMMEDIATE`:
`aurora.db` (reservas, visitantes, códigos emitidos, índice de sessões) e `sessions.db` (sessões e eventos do ADK).
`dados/` é só leitura: serve de seed e de fonte para a restauração.

---

## Garantias

| # | Garantia | Onde mora |
| :--- | :--- | :--- |
| G1 | Cobrança ou acesso só com confirmação | `agentes/ferramentas_*.py`, `dominio/areas.py`, `conversa/servico.py` |
| G2 | Cada sessão pertence a um apartamento | `agentes/identidade.py`, `conversa/servico.py`, `agentes/serializacao.py` |
| G3 | Nada se perde no reinício | `conversa/sessoes.py`, `ciclo_de_vida/inicializacao.py`, `persistencia/` |
| G4 | Regulamento consultado, não carregado | `regulamento/`, `agentes/instrucoes.py` |
| G5 | Dois moradores, uma reserva | `persistencia/esquema.py`, `persistencia/repositorio_reservas.py` |

### G1: cobrança ou acesso só com confirmação

- **Declaração:** [`ferramentas_reservas.py:64-72`](src/aurora/agentes/ferramentas_reservas.py) liga `reservar_area` a
  `require_confirmation=reserva_gera_cobranca`, e [`ferramentas_visitantes.py:29`](src/aurora/agentes/ferramentas_visitantes.py)
  declara `autorizar_visitante` com `require_confirmation=True`. É o mecanismo nativo do ADK: a tool **nem executa** sem
  um `FunctionResponse` de confirmação.
- **Decisão de cobrança no código:** o predicado chama [`CatalogoAreas.exige_confirmacao`](src/aurora/dominio/areas.py)
  (`areas.py:34-37`), que lê a taxa de `areas.json` e é *fail-closed* (área desconhecida também exige confirmação).
  A quadra (taxa 0) executa direto; cancelamento nunca pede confirmação.
- **A confirmação vem do sistema, não da conversa:** a pendência é a chamada `adk_request_confirmation` sem resposta
  nos eventos persistidos ([`pendencias.py:21`](src/aurora/conversa/pendencias.py)). Só a rota `POST /confirmacoes`
  produz o `FunctionResponse` ([`servico.py:84-100`](src/aurora/conversa/servico.py)). "Já confirmei" no chat não muda
  nada porque o modelo não tem como produzir esse evento.
- **`409`:** [`servico.py:88-90`](src/aurora/conversa/servico.py) rejeita, **antes** de chamar o `Runner`, qualquer `id`
  que não esteja pendente naquela sessão (inexistente, já respondido ou de outra sessão). O reenvio é barrado porque o
  `FunctionResponse` gravado torna o `id` "respondido", inclusive após reiniciar.

### G2: cada sessão pertence a um apartamento

- **Uma única vez, na criação:** [`servico.py:56-59`](src/aurora/conversa/servico.py) cria a sessão com
  `user_id = apartamento`, e o índice `session_id → apartamento` ([`indice_sessoes.py`](src/aurora/persistencia/indice_sessoes.py))
  decide a quem a sessão pertence.
- **Tools sem parâmetro de apartamento:** o apartamento vem de `tool_context.user_id`
  ([`identidade.py:14`](src/aurora/agentes/identidade.py)). Nenhuma das 7 tools declara esse parâmetro; um teste
  inspeciona assinaturas e declarações enviadas ao modelo (`tests/agentes/test_agentes.py`).
- **Nenhum dado de terceiros chega ao modelo:** o filtro por apartamento está no SQL
  ([`repositorio_reservas.py`](src/aurora/persistencia/repositorio_reservas.py), `_cancelar`), e reserva de outro
  apartamento é indistinguível de reserva inexistente (`NaoEncontrada`). A disponibilidade devolve só `livre`/`ocupada`
  ([`serializacao.py:24`](src/aurora/agentes/serializacao.py), `Disponibilidade`), e `Indisponivel` não carrega dono
  nem código. `serializar` é um `match` exaustivo: um tipo novo sem mapeamento falha em teste, não em produção.

### G3: nada se perde no reinício

- **Sessões e eventos:** [`sessoes.py:17`](src/aurora/conversa/sessoes.py) usa `DatabaseSessionService` sobre
  `var/sessions.db`. As pendências são derivadas desses eventos, então também sobrevivem.
- **Domínio:** reservas, visitantes e códigos ficam em `var/aurora.db`. O seed só é aplicado se o marcador
  `seed_aplicado` não existir ([`inicializacao.py:23`](src/aurora/ciclo_de_vida/inicializacao.py)); a subida **nunca**
  restaura. Só `aurora-restaurar` volta ao estado de `dados/`
  ([`restauracao.py:22`](src/aurora/ciclo_de_vida/restauracao.py)).
- **Códigos nunca repetem:** a tabela `codigos_reserva` é gravada na mesma transação da reserva e **nunca é apagada**,
  nem na restauração ([`carga_inicial.py:58`](src/aurora/persistencia/carga_inicial.py)); cancelar é *soft delete*.
  O formato `RSV-XXXXXX` ([`codigos.py:11`](src/aurora/dominio/codigos.py)) não colide com os iniciais (`RSV-NNNN`).

### G4: regulamento consultado, não carregado

- **O `concierge` não recebe o regulamento:** [`instrucoes.py:17`](src/aurora/agentes/instrucoes.py) só descreve o
  papel; o texto só é lido pelo índice do especialista. Um teste confere que nenhuma linha longa do regulamento aparece
  nas instruções.
- **Um capítulo por consulta:** [`ferramenta_capitulo.py:32`](src/aurora/regulamento/ferramenta_capitulo.py) restringe
  o parâmetro `capitulo` a um enum fechado com os 14 ids; as instruções do especialista
  ([`instrucoes.py:22`](src/aurora/regulamento/instrucoes.py)) listam só id e título.
- **Isolamento:** o especialista roda como `AgentTool` ([`agente.py:45`](src/aurora/regulamento/agente.py)), numa sessão
  em memória descartada. Os eventos da sessão principal contêm apenas a chamada `regulamento` e a resposta curta; o
  roteiro de aceitação (passo 12) confere que nenhum trecho de outro capítulo aparece neles.

### G5: dois moradores, uma reserva

- **Restrição no armazenamento:** [`esquema.py:18`](src/aurora/persistencia/esquema.py) cria o índice único parcial
  `ux_reserva_ativa ON reservas(area_id, data) WHERE status = 'ativa'`. A exclusividade vale **no instante da
  gravação**, qualquer que seja a ordem ou o caminho de código; não há *check-then-insert* nem lock em memória
  ([`servico_reservas.py`](src/aurora/dominio/servico_reservas.py), `reservar`).
- **Conflito é resposta normal:** [`repositorio_reservas.py:28-58`](src/aurora/persistencia/repositorio_reservas.py)
  captura a violação do índice, desfaz a transação (o código não fica emitido) e devolve `Indisponivel`; a rota
  responde `200`.
- **Sem `database is locked`:** [`sqlite.py:25-32`](src/aurora/infra/sqlite.py) aplica WAL, `busy_timeout` e
  `BEGIN IMMEDIATE` em toda conexão. Testes: 20 chamadas concorrentes dão exatamente 1 reserva; duas aprovações
  simultâneas em sessões diferentes respondem `200` e somam 1 reserva.
- **Concorrência por sessão:** [`travas.py:17`](src/aurora/conversa/travas.py) serializa operações da mesma sessão;
  sessões diferentes correm em paralelo (processo único, [ADR-017](docs/adr/ADR-017-api-e-modelo-de-execucao.md)).

---

## Como rodar

### Pré-requisitos

- Python 3.12+ e [uv](https://docs.astral.sh/uv/)
- Uma chave do [Google AI Studio](https://aistudio.google.com/apikey)
- Nenhum serviço externo: o armazenamento é SQLite em `var/`

### Variáveis do `.env`

```bash
cp .env.example .env   # e preencha GOOGLE_API_KEY
```

| Variável | Obrigatória | Uso |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | Sim | Chave do Google AI Studio |
| `GOOGLE_GENAI_USE_VERTEXAI` | Não | Use `FALSE` (Google AI Studio, não Vertex) |
| `AURORA_MODELO` | Não | Modelo Gemini; padrão `gemini-3.8-flash` |

### Comandos

```bash
uv sync                     # instala o projeto
uv run aurora-restaurar     # volta reservas e visitantes ao estado de dados/ (e apaga as sessões)
uv run aurora-api           # sobe a API em http://localhost:8000 (Ctrl+C para parar)
```

- A subida **não** restaura os dados: reiniciar a API preserva sessões, reservas e visitantes. Num clone limpo, o
  primeiro `aurora-api` já semeia o banco; `aurora-restaurar` é o caminho para voltar ao estado inicial.
- Pare a API antes de restaurar (o comando avisa e sai com código 2 se o banco estiver travado).

```bash
curl -s localhost:8000/apartamentos/101/reservas
curl -s -X POST localhost:8000/sessoes -H 'content-type: application/json' -d '{"apartamento":"101"}'
```

### Testes

```bash
uv run pytest                                                    # unitários e integração (sem Gemini)
AURORA_ACEITACAO=1 uv run pytest tests/aceitacao -m aceitacao -v -s   # fluxo do avaliador contra a API real
```

A suíte de aceitação sobe e derruba a API sozinha (porta 8000 livre) e consome cota do Gemini.
