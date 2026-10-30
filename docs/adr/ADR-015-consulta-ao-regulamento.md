# ADR-015 — Consulta ao regulamento por capítulo, com seleção por identificador fechado e execução isolada

- **Status:** Proposto
- **Data da decisão:** 2026-10-30
- **Decisores:** Lucas Rocha (responsável pela entrega)
- **Relacionados:**
  - **Depende de:** [ADR-003](ADR-003-topologia-de-agentes.md) (o especialista `regulamento` roda como `AgentTool`, em sessão aninhada descartada), [ADR-001](ADR-001-regras-em-camada-de-dominio.md) (o serviço de regulamento é parte do domínio)
  - **Influencia:** [ADR-018](ADR-018-modelos-gemini.md) (custo por consulta)
  - **Referências:** [ENUNCIADO — Garantia 4](../../ENUNCIADO.md#5-garantia-4-o-regulamento-é-consultado-não-carregado), [SUMMARY GT-04 e §4.5](../SUMMARY.md#45-regulamento--dadosregulamentomd), [PRD — RF-010](../PRD.md#rf-010-tirar-dúvidas-sobre-o-regulamento)

## Contexto

O `dados/regulamento.md` tem cerca de 44 KB, 491 linhas e **14 capítulos** com cabeçalhos uniformes (`## Capítulo <romano>: <tema>`) e artigos numerados.

G4 exige três coisas:

- o agente principal **não recebe o regulamento nas instruções**;
- **nenhum evento da sessão contém trechos de capítulos que tratam de outros assuntos**;
- a resposta usa o texto oficial. No passo 12: "Até que horas a piscina funciona aos domingos?" → **20h** (Art. 22, II). De segunda a sábado a piscina fecha às 22h.

Armadilha conhecida (GT-04): termos genéricos da pergunta ("horas", "funciona") também aparecem nos capítulos III (silêncio), V (academia e playground, que também fecha às 20h), IX (mudanças) e X (obras). Uma busca por palavra-chave traria capítulos errados para o histórico.

## Decisão

1. Na inicialização, o serviço de regulamento **indexa o arquivo por capítulo** a partir dos cabeçalhos `## Capítulo`. Cada capítulo recebe um identificador estável (ex.: `IV-piscina`), um título e o texto completo. A indexação é determinística e não usa modelo.
2. A tool **`consultar_capitulo(capitulo)`** recebe um **identificador de um conjunto fechado** (enum com os 14 capítulos) e devolve **o texto de um único capítulo**. Não há busca livre por texto.
3. A **lista de capítulos** (identificador e título) fica **nas instruções do especialista `regulamento`**, não numa tool. Instruções não são eventos, então nem os títulos de outros capítulos entram no histórico.
4. O especialista roda como **`AgentTool`** ([ADR-003](ADR-003-topologia-de-agentes.md)):
   - a chamada à tool e o texto do capítulo ficam na sessão aninhada, que é descartada;
   - na sessão principal entra só a **resposta final**, com o trecho pertinente e a citação do artigo (ex.: "Art. 22, II: aos domingos e feriados, das 9h às 20h").
5. Instruções do especialista:
   - escolher o capítulo pelo **tema** da pergunta;
   - responder **apenas** com base no capítulo consultado, citando o artigo;
   - dizer que não encontrou a regra quando ela não existir;
   - consultar mais de um capítulo **somente** se a pergunta envolver mais de um tema.
6. O agente principal conhece apenas a **descrição** do especialista ("responde dúvidas sobre o regulamento interno"), nunca o texto.

## Alternativas consideradas

### A1. Regulamento inteiro nas instruções do especialista
- **Prós:** sem indexação; o modelo vê tudo e escolhe.
- **Contras:** cerca de 11 mil tokens a cada consulta; contraria a ideia de "consultado, não carregado"; aumenta o risco de o modelo citar trechos de outros capítulos na resposta final, que é gravada como evento.
- **Motivo do descarte:** custo e risco maiores, sem ganho de precisão.

### A2. Busca por palavra-chave ou BM25 sobre artigos
- **Prós:** sem depender do modelo para escolher o capítulo.
- **Contras:** cai exatamente na armadilha GT-04 (termos genéricos presentes em vários capítulos); a ordenação por relevância é instável.
- **Motivo do descarte:** risco alto de trazer capítulos de outros assuntos.

### A3. RAG com embeddings e base vetorial
- **Prós:** busca semântica robusta para documentos grandes.
- **Contras:** infraestrutura e chamadas extras (modelo de embeddings, índice); pode misturar trechos de capítulos diferentes no top-k; é exagero para 14 capítulos bem delimitados.
- **Motivo do descarte:** complexidade desproporcional e risco de mistura de capítulos.

### A4. Recorte por artigo (granularidade menor)
- **Prós:** menos tokens por consulta.
- **Contras:** os artigos não têm título, então o modelo teria de escolher sem ver o conteúdo; seria preciso um índice semântico por artigo; aumenta o risco de faltar contexto (parágrafos e incisos relacionados).
- **Motivo do descarte:** o capítulo é a unidade temática natural do documento.

### A5. Especialista de regulamento como sub-agente `chat` (sem isolamento)
- **Prós:** mecanismo uniforme com os outros especialistas.
- **Contras:** o capítulo devolvido pela tool fica no histórico da sessão principal e acompanha as chamadas seguintes; com a ferramenta por capítulo ele não viola G4, mas perde a defesa em profundidade e encarece os turnos seguintes.
- **Motivo do descarte:** detalhado no [ADR-003](ADR-003-topologia-de-agentes.md).

## Consequências

### Positivas
- **Duas camadas de proteção** para G4: a seleção fechada por capítulo e a execução isolada.
- Custo por pergunta limitado a um capítulo (alguns KB), pago só quando há dúvida sobre o regulamento.
- Comportamento determinístico na parte de recorte; o modelo só escolhe o tema.

### Negativas
- Depende da estrutura de cabeçalhos do arquivo; uma mudança de formato exige ajustar o indexador (o arquivo é imutável no desafio).
- Uma pergunta que cruze temas exige mais de uma consulta.
- A resposta final do especialista entra no histórico, então as instruções precisam mantê-la concisa e restrita ao tema.

### Trade-off explícito
Abre-se mão de busca livre e de granularidade fina em troca de um recorte **previsível e isolado**, que torna inviável levar ao histórico trechos de capítulos de outros assuntos.
