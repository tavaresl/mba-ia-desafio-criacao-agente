# Feature Design Document (FDD): Serviços de domínio de reservas e visitantes

---
**Versão:** v1.0  
**Data:** 2026-10-30  
**Responsável:** Lucas Rocha  
**Status:** Rascunho  
**ADRs implementados:** [ADR-001](../adr/ADR-001-regras-em-camada-de-dominio.md), [ADR-005](../adr/ADR-005-mecanismo-de-confirmacao.md) (política de confirmação), [ADR-010](../adr/ADR-010-minimizacao-de-dados-nas-tools.md) (resultados mínimos), [ADR-014](../adr/ADR-014-codigos-de-reserva.md) (geração do código)  
**Depende de:** [FDD-01](FDD-01-fundacao-e-contratos.md) (os `Protocol`s de repositório e serviço, os DTOs e os fakes para os testes)  
**Consumido por:** FDD-06 (tools), FDD-08 (rotas de verificação e montagem). Ambos usam os `Protocol`s de `aurora.contratos.servicos`.  
---

## 1. Contexto e motivação técnica

O [ADR-001](../adr/ADR-001-regras-em-camada-de-dominio.md) decidiu que as regras críticas vivem num **domínio determinístico, sem ADK e sem modelo**. As tools (FDD-06) apenas repassam a chamada a ele. Este FDD é esse domínio para reservas e visitantes:

- valida e normaliza a entrada vinda do modelo (nome de área, data, nome de visitante);
- aplica RN-01 a RN-05;
- decide **quais ações exigem confirmação** (taxa > 0, com fail-closed);
- devolve apenas os tipos de resultado mínimos definidos no FDD-01.

Ser puro (sem I/O próprio, com repositórios injetados por construtor) torna as regras testáveis de forma isolada, como pede a skill `python-design-patterns` (*Dependency Injection*, *don't mix I/O with business logic*).

---

## 2. Objetivos técnicos

* Implementar `ServicoReservas` e `ServicoVisitantes` conforme os `Protocol`s do FDD-01.
* Implementar `CatalogoAreas`: a normalização de nome de área para `id` e a política `exige_confirmacao`, síncrona e **fail-closed**.
* Implementar `gerar_codigo_reserva()`: o formato `RSV-` + 6 caracteres do alfabeto Crockford base32, gerados com `secrets`.
* Garantir que **todo** método recebe o apartamento como parâmetro obrigatório e repassa o filtro ao repositório.
* Cobrir as regras com testes unitários usando só os fakes do FDD-01.

---

## 3. Escopo e exclusões

### Incluído
* `aurora/dominio/areas.py`: `CatalogoAreas`, com `resolver(texto) -> Area | None` e `exige_confirmacao(texto) -> bool`.
* `aurora/dominio/validacao.py`: `interpretar_data(texto) -> date | None` (ISO `AAAA-MM-DD`) e `normalizar_nome_visitante(texto) -> str | None`.
* `aurora/dominio/codigos.py`: `gerar_codigo_reserva()`.
* `aurora/dominio/servico_reservas.py`: `ServicoReservasPadrao`.
* `aurora/dominio/servico_visitantes.py`: `ServicoVisitantesPadrao`.
* `aurora/dominio/__init__.py`, com `__all__`.

### Excluído
* SQL e transações (FDD-02).
* De onde vem o apartamento: aqui ele é só um parâmetro; a extração do contexto da sessão é do FDD-06 ([ADR-009](../adr/ADR-009-identidade-do-apartamento.md)).
* Conversão para dicionários das tools e textos ao morador (FDD-06).
* Antecedência, datas passadas, horários e capacidade (fora de escopo pelo enunciado).

---

## 4. Fluxos detalhados e diagramas

* **Fluxo A: normalização de área** (`CatalogoAreas.resolver`).
  1. Normalizar o texto: minúsculas, sem acentos (`unicodedata.normalize("NFKD")`), espaços e hífens unificados.
  2. Procurar correspondência exata com o `id` (`salao-de-festas`) ou com o `nome` normalizado (`salao de festas`).
  3. Aceitar **apenas** correspondências exatas após a normalização, sem *fuzzy matching*. Se não houver correspondência, `None`.

  > A lista de áreas é carregada uma única vez na montagem (dado de referência imutável), o que permite que `exige_confirmacao` seja síncrono.

* **Fluxo B: política de confirmação** (`exige_confirmacao(area)`, fail-closed).

```python
def exige_confirmacao(self, area: str) -> bool:
    encontrada = self.resolver(area)
    return encontrada is None or encontrada.taxa > 0   # só dispensa se for área conhecida com taxa 0
```

* **Fluxo C: reservar** (`ServicoReservasPadrao.reservar`).
  1. `area = catalogo.resolver(area)`; se `None`, devolve `EntradaInvalida(AREA_INEXISTENTE)`.
  2. `data = interpretar_data(data)`; se `None`, devolve `EntradaInvalida(DATA_INVALIDA)`.
  3. `await reservas.criar(apartamento=..., area_id=area.id, data=data, gerar_codigo=self._gerar_codigo)`.
  4. Devolve `ReservaCriada` ou `Indisponivel` tal como vierem do repositório.

  > O serviço **não** faz checagem prévia de ocupação: a garantia está na gravação ([ADR-013](../adr/ADR-013-exclusividade-de-reserva.md)). A checagem prévia existe só como consulta separada (`consultar_disponibilidade`).

* **Fluxo D: cancelar** (`cancelar`).
  - Com `codigo`: `cancelar_por_codigo(apartamento, codigo.upper().strip())`.
  - Com `area` e `data`: valida as duas e chama `cancelar_ativa(...)`.
  - Sem identificação suficiente: `EntradaInvalida(IDENTIFICACAO_INCOMPLETA)`.
  - Em qualquer caso, reserva de terceiro resulta em `NaoEncontrada`, decidido pelo filtro do repositório.
* **Fluxo E: autorizar visitante** (`ServicoVisitantesPadrao.autorizar`). Valida o nome (não vazio após `strip`, até 100 caracteres, sem caracteres de controle) e a data; então `repositorio.autorizar(...)` e retorna `VisitanteAutorizado(nome, data)`.

---

## 5. Contratos públicos (assinaturas, headers, exemplos)

### 5.1 Interface pública

```python
# src/aurora/dominio/__init__.py
__all__ = ["CatalogoAreas", "ServicoReservasPadrao", "ServicoVisitantesPadrao",
           "gerar_codigo_reserva", "interpretar_data"]

class CatalogoAreas:
    def __init__(self, areas: Sequence[Area]) -> None: ...
    def listar(self) -> list[Area]: ...
    def resolver(self, texto: str) -> Area | None: ...
    def exige_confirmacao(self, texto: str) -> bool: ...

class ServicoReservasPadrao:                       # implementa aurora.contratos.ServicoReservas
    def __init__(self, *, reservas: RepositorioReservas, areas: CatalogoAreas,
                 gerar_codigo: Callable[[], str] = gerar_codigo_reserva) -> None: ...

class ServicoVisitantesPadrao:                     # implementa aurora.contratos.ServicoVisitantes
    def __init__(self, *, visitantes: RepositorioVisitantes) -> None: ...

def gerar_codigo_reserva() -> str: ...             # ex.: "RSV-7K2Q9M"
```

### 5.2 Semântica dos contratos de resposta
* Os métodos **nunca** levantam exceção para desfechos de negócio; devolvem os tipos `Resultado*` do FDD-01.
* `consultar_disponibilidade` devolve `Disponibilidade(area_id, data, disponivel)`, **sem** dono nem código.
* `listar_do_apartamento` devolve apenas registros do apartamento informado.
* `exige_confirmacao` é a **única fonte** da decisão "esta reserva gera cobrança". O FDD-06 a usa como predicado de `require_confirmation`.
* `resolver_area` e `listar_areas` delegam ao `CatalogoAreas`, e o `DescritorAcoesPadrao` (FDD-06) usa o mesmo `resolver_area` para preencher `detalhes`. Assim, predicado, corpo da tool e pendência veem a mesma área.

### 5.3 Exemplos de uso

```python
areas = CatalogoAreas(await repos.referencia.listar_areas())
servico = ServicoReservasPadrao(reservas=repos.reservas, areas=areas)

areas.exige_confirmacao("quadra")             # False
areas.exige_confirmacao("Salão de Festas")    # True
areas.exige_confirmacao("piscina")            # True (fail-closed; a reserva depois falha como AREA_INEXISTENTE)

await servico.cancelar(apartamento="101", area="salão de festas", data="2030-03-16")
# -> NaoEncontrada()   (a reserva da data é do 302; nada é revelado)
```

---

## 6. Configuração e opções

* **Requisitos de Runtime:** Python 3.12+ (biblioteca padrão: `secrets`, `unicodedata`, `datetime`, `decimal`).
* **Armazenamento / Dependências de Infra:** nenhuma; tudo é injetado.
* **Variáveis de ambiente e parâmetros:** nenhum.

```python
ALFABETO_CODIGO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # Crockford base32
TAMANHO_CODIGO = 6
TAMANHO_MAXIMO_NOME_VISITANTE = 100
```

---

## 7. Erros, exceções e fallback

### 7.1 Concorrência e atomicidade
* **Por que é crítico:** reservas concorrentes. A tentação seria checar a ocupação e depois inserir.
* **Garantias:** o serviço não mantém estado mutável e não faz *check-then-insert*. A atomicidade é delegada à restrição do FDD-02, e o serviço apenas repassa `Indisponivel`.

### 7.2 Tratamento de erros gerais
| Situação de Erro | Tratamento Técnico / Comportamento |
| :--- | :--- |
| Área desconhecida | `EntradaInvalida(AREA_INEXISTENTE)` |
| Data fora de `AAAA-MM-DD` ou inexistente (`2030-02-30`) | `EntradaInvalida(DATA_INVALIDA)` |
| Nome de visitante vazio, longo demais ou com caracteres de controle | `EntradaInvalida(NOME_INVALIDO)` |
| Cancelamento sem código nem área e data | `EntradaInvalida(IDENTIFICACAO_INCOMPLETA)` |
| Exceção vinda do repositório | Propaga sem tratamento (falha de sistema; o FDD-08 decide o status HTTP) |

### 7.3 Modo permissivo (Fallback / Fail-Open)
* **Fail-closed** na política de confirmação: em qualquer dúvida sobre a área, a confirmação é exigida.

---

## 8. Métricas, logs e tracing
* **Métricas:** fora de escopo.
* **Logs estruturados:** o domínio **não loga** (sem I/O próprio). Os logs de operação ficam no repositório (FDD-02) e na conversa (FDD-07).
* **Tracing:** não aplicável.

---

## 9. Dependências e compatibilidade
| Componente | Versão mínima | Observações |
| :--- | :--- | :--- |
| Python | 3.12 | Somente biblioteca padrão |
| **FDD-01** | — | `Protocol`s, DTOs, `MotivoInvalido` e fakes de repositório para os testes |
| **FDD-02** | — | Implementação real dos repositórios, ligada só na montagem (FDD-08); **não bloqueia** o desenvolvimento |

---

## 10. Critérios de aceite técnicos
* [ ] `exige_confirmacao` devolve `False` **somente** para `quadra` (taxa 0) e suas variações de escrita; `True` para salão, churrasqueira e qualquer texto desconhecido.
* [ ] `reservar` numa data ocupada devolve `Indisponivel` sem nenhum dado do ocupante.
* [ ] `cancelar` de uma reserva de outro apartamento devolve `NaoEncontrada` e não altera nada (verificado no fake).
* [ ] `gerar_codigo_reserva()` sempre casa com `^RSV-[0-9A-HJKMNP-TV-Z]{6}$` e nunca produz um dos códigos iniciais.
* [ ] `aurora.dominio` não importa `google.adk`, `sqlalchemy` nem `fastapi`.
* [ ] Cobertura de testes unitários ≥ 90% no pacote `aurora.dominio`.

---

## 11. Riscos e mitigação
| Risco | Impacto | Mitigação |
| :--- | :--- | :--- |
| O modelo enviar a área em formatos não previstos ("salão", "festa") | Médio | Retornar `AREA_INEXISTENTE`; a instrução do especialista (FDD-06) lista os `id`s válidos, e a tool `listar_areas` está disponível |
| Normalização divergente entre o predicado e o corpo da tool | Alto | Ambos usam **o mesmo** `CatalogoAreas.resolver`, com um teste cobrindo os dois caminhos |
| Validação de nome restritiva demais (nomes compostos ou com acento) | Baixo | Aceitar qualquer caractere imprimível; rejeitar só vazio, longo demais ou controle |
