# ADR-014 — Códigos de reserva: aleatórios, gerados pelo sistema, com registro permanente de códigos emitidos

- **Status:** Aceito (implementado e validado em 2026-10-30: testes de integração, PoCs de confirmação e roteiro de aceitação com o Gemini real)
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-012](ADR-012-armazenamento-do-dominio.md) (tabela `codigos_reserva`), [ADR-013](ADR-013-exclusividade-de-reserva.md) (cancelamento lógico)
  - **Influencia:** [ADR-016](ADR-016-ciclo-de-vida-dos-dados.md) (a restauração não apaga o registro de códigos)
  - **Referências:** [SUMMARY RN-05, GT-12](../SUMMARY.md#5-regras-de-negócio), [ENUNCIADO — Regras de negócio](../../ENUNCIADO.md#regras-de-negócio) (regra 5), passo 13 do fluxo do avaliador

## Contexto

RN-05 diz que o código de uma reserva nova é **gerado pelo sistema**, em formato livre, e **nunca repete o código de outra reserva, inclusive de uma cancelada**.

No passo 13, o avaliador confere que:

- os códigos criados no fluxo são diferentes entre si;
- eles são diferentes dos iniciais `RSV-1377`, `RSV-4821` e `RSV-2950`.

Os códigos iniciais têm o formato `RSV-` + 4 dígitos (espaço de 10 mil valores).

O comando de restauração ([ADR-016](ADR-016-ciclo-de-vida-dos-dados.md)) recria as reservas a partir de `dados/`. Se a unicidade dependesse apenas da tabela de reservas, todo código emitido antes de uma restauração seria "esquecido" e poderia voltar a ser gerado.

## Decisão

1. Formato **`RSV-` + 6 caracteres** de um alfabeto sem caracteres ambíguos (base32 de Crockford, ex.: `RSV-7K2Q9M`), gerados com `secrets`. O formato difere do inicial (4 dígitos), o que elimina por construção a colisão com os códigos de `dados/`.
2. A tabela **`codigos_reserva`** registra **todo código já emitido**, inclusive os iniciais carregados no seed. A coluna `codigo` é a chave primária.
3. A emissão insere o código no registro **na mesma transação** que cria a reserva. Em caso de colisão (violação de chave primária), gera-se outro código, com um número limitado de tentativas.
4. **A restauração não apaga o registro de códigos.** Os códigos de `dados/` são reinseridos de forma idempotente (`ON CONFLICT DO NOTHING`).
5. As reservas canceladas permanecem na tabela de reservas (cancelamento lógico, conforme o [ADR-013](ADR-013-exclusividade-de-reserva.md)).
6. **Nenhuma tool aceita código de reserva para criação**: o modelo nunca escolhe o código.

## Alternativas consideradas

### A1. Sequencial (`RSV-<n>`, a partir do maior existente + 1)
- **Prós:** legível; ordenado.
- **Contras:** se o contador derivar da tabela de reservas, a restauração o "rebobina" e repete códigos; um contador persistido resolve isso, mas os códigos ficam **previsíveis**, o que facilita tentar adivinhar reservas de outros (a checagem de dono impede o efeito, mas aumenta a superfície).
- **Motivo do descarte:** a previsibilidade e o acoplamento à restauração não compensam a legibilidade.

### A2. UUID4 completo
- **Prós:** unicidade prática sem coordenação.
- **Contras:** 36 caracteres, ruim para ler e repetir numa conversa de chat.
- **Motivo do descarte:** experiência ruim para o morador.

### A3. `RSV-` + 4 dígitos aleatórios, igual ao formato inicial
- **Prós:** consistente com os dados existentes.
- **Contras:** espaço pequeno (10 mil valores); colisão possível com os códigos iniciais; exige mais tentativas à medida que o histórico cresce.
- **Motivo do descarte:** risco desnecessário de colisão.

### A4. Unicidade só na tabela de reservas, sem registro separado
- **Prós:** uma tabela a menos.
- **Contras:** a restauração apaga reservas criadas e canceladas, e os códigos delas voltam a ficar "livres".
- **Motivo do descarte:** viola RN-05 entre ciclos de restauração.

## Consequências

### Positivas
- Unicidade garantida pelo banco (chave primária), inclusive entre restaurações.
- Códigos curtos e legíveis, sem previsibilidade.
- Colisão com os códigos iniciais é impossível por formato e também pelo registro.

### Negativas
- Uma tabela extra, que cresce para sempre (irrelevante no volume do desafio).
- O formato dos códigos novos difere do formato dos códigos iniciais.

### Trade-off explícito
Aceita-se uma tabela adicional e um formato diferente do inicial em troca de uma unicidade que **sobrevive à restauração** e não depende de contador.
