# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; Classification Layer v0.1 contratada em 0022 e **implementada, auditada, mergeada e congelada em 0023**.

Validação corrente:
- parser v0.4: **102/102**;
- parser + Analysis v0.1a: **154/154**;
- Analysis até v0.1b Marco 1: **222/222**;
- Analysis completa: **267/267**;
- após Decision Layer v0.1: **290/290**;
- após Classification Layer v0.1: **335/335**;
- failures: 0;
- errors: 0;
- skips: 0.

PRs/freeze principais:
- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1; head auditado `c340d1ab2c94b7c4af802419d0e414c4019be246`; squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021;
- PR #6 — Classification Layer v0.1; head final auditado `94fb797fec1f44508274ec47ba87409da8e4537d`; squash `736c33036224562549b1b5cb026bd6bfdfd2e112`; freeze 0023.

Este é o HANDOFF corrente. O histórico fica no Git; não criar `handoff_vNN`.

## Regra operacional

**Tudo o que puder ser corrigido com segurança dentro do escopo atual deve ser corrigido antes de avançar.**

Só postergar quando houver expansão explícita de escopo, dependência não resolvida, impossibilidade técnica demonstrada, contradição normativa/arquitetural nova ou novo risco de segurança.

Fluxo formal:
1. ChatGPT propõe;
2. modelo apropriado audita;
3. ChatGPT integra;
4. Felipe aprova quando necessário;
5. HANDOFF + decisão/commit.

Para Kimi:
- novo chat por etapa técnica grande;
- sempre começar com HANDOFF + SHA exato do `main` + tarefa fechada;
- implementação só conta com branch/commit/PR real ou diff completo;
- GitHub remoto é fonte de verdade;
- auditoria adversarial antes de merge/freeze.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado. Não promete conformidade ABNT genérica.

Saídas previstas:
1. DOCX limpo;
2. DOCX de revisão;
3. relatório.

Princípio: **Na dúvida, marcar.**

## Segurança congelada

- nenhuma invenção/perda substantiva;
- só atuar em subaspecto autorizado;
- ambiguidade não é resolvida silenciosamente;
- opacos são preservados/protegidos;
- SafetyGate é veto, nunca autorização;
- C3 exige revisão humana;
- classificação errada é risco upstream: **precision > coverage**;
- abstention correta é sucesso seguro.

## Corpus-base v1

- 41 fixtures;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo e alteração indevida de citação direta.

## Physical layer / parser — 0001–0012

Congelado:
- OriginalPackage imutável;
- PhysicalIR serializável/forense;
- OOXML+lxml autoritativo;
- saída nunca reconstruída da IR;
- stories secundárias, parse parcial, tabelas, nested tables e block containers;
- parser v0.4.0;
- suíte: **102/102**.

## Analysis View v0.1a — 0013–0014

Congelada:
- segmentos físicos autoritativos;
- `default_text` derivado;
- offsets em code points Python;
- não-participantes zero-width;
- opacos preservados;
- serialização determinística;
- sem live lxml;
- PhysicalIR imutável.

## Analysis View v0.1b — 0015–0018

Marco 1:
- run: `w:sz`, `w:rFonts` 8 slots, `w:lang` 3 slots, `w:u`, `w:vertAlign`;
- paragraph: `pStyle`, `w:jc`, `w:spacing`, `w:ind` com cláusula numbering↔indent;
- regras de defaults/styleId conforme 0016.

Marco 2:
- `w:b`, `w:i`;
- styles/docDefaults: `docDefaults -> paragraph root→specific -> character root→specific`;
- toggle correto em styles; direct absoluto e terminal;
- `w:val=""` inválido;
- tudo ausente => `absent`, nunca false;
- duplicates/cycles/evidence conforme 0018.

Suíte Analysis completa: **267/267**.

## Decision Vocabulary v0.1 — 0019

`decision_vocabulary_version = "0.1"`

```text
P1 / run / bold
P1 / run / italic
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

DecisionKey = `(target_type, aspect_id, property_slot)`.

Registry versionado é a fronteira única Analysis→Decision.

## Decision Layer v0.1 — 0020 + freeze 0021

Pipeline:

```text
Analysis View
+ TargetClassification
+ profile/rule context validado
-> Decision
```

Dois eixos:

```text
ComplianceStatus:
    compliant
    non_compliant
    unknown
    not_applicable
    not_evaluated

Actionability:
    no_action
    deterministic_change
    human_choice
    review
    preserve
```

Invariante:

```text
desired_value != None
IFF
actionability == deterministic_change
```

Slice executável congelado:

```text
P1/run/bold
P2/run/font_size
P3/paragraph/spacing.line
P4/paragraph/alignment
```

Estados seguros:
- rule absent -> preserve, `rule_ref=None`;
- containment -> preserve com rule concreta;
- absent/unresolved/invalid/ambiguous com regra ativa -> unknown/review;
- `absent` nunca equivale a false;
- set/preferred/human_choice conforme 0020/0021.

Suíte após Decision: **290/290**.

## Classification Layer v0.1 — 0022 + freeze 0023

Pipeline congelado:

```text
PhysicalIR + StyleCatalog
-> Analysis pública determinística (derivada internamente)
-> ClassificationResult
-> TargetClassification elegível
-> Decision Layer
```

### Escopo executável

```text
body
heading
abstain / not_applicable
```

No vocabulário, mas ainda não executáveis:

```text
long_quote
reference
```

`unknown` NÃO é `target_class`.

### Status / basis

```text
ClassificationStatus:
    classified
    abstained
    not_applicable

ClassificationBasis:
    explicit
    structural
    heuristic
```

Elegibilidade automática é derivada:

```text
status == classified
AND basis in {explicit, structural}
```

Sem confidence numérico e sem `safe_for_automatic_use` redundante.

### Style identity map v0.1

Mapa congelado:

```text
Normal -> body
Heading1..Heading9 -> heading level N
```

`BodyText` ficou fora por ausência de evidência real suficiente.

Regras:
- styleId exato;
- `style_type=paragraph` obrigatório;
- `customStyle=true` impede identidade built-in direta;
- style name sozinho nunca classifica;
- custom style pode herdar via `basedOn` válida;
- cycle/dangling/wrong-type hop não classificam.

### Default paragraph style

`pStyle` ausente pode usar o default paragraph style aplicável do StyleCatalog como evidência positiva.

Esse sinal é `basis=explicit`, com evidence própria `default_paragraph_style`.

### Body

Nunca fallback residual.

Sem identidade reconhecida, o documento pode resultar em 100% abstention.

### Heading

`HeadingN`:

```text
target_class = heading
metadata.level = N
basis = explicit
reason = explicit_style_signal
```

Aparência tipográfica não classifica.

### Context policies

- secondary stories -> not_applicable/unsupported_story;
- table/cell/nested/block_container -> abstained/unsupported_context;
- numbering warning -> abstained/unsupported_context;
- empty paragraph -> abstained/empty_content;
- empty_content tem prioridade sobre unsupported_context.

### Run inheritance

Runs só recebem classe por projeção explícita do parágrafo pai.

Após auditoria, ficou congelado:
- run path deve ser descendente estrito do paragraph path;
- run de outro parágrafo = erro de contrato;
- prefix siblings não contam como parentesco;
- run herdado preserva path/hash próprios, parent_anchor e provenance distinta.

### basedOn type-boundary

A auditoria encontrou e corrigiu cadeia que atravessava style de tipo errado.

Regra congelada:
- qualquer hop `style_type != paragraph` quebra a cadeia;
- identidade além dessa fronteira é proibida.

### API

```text
classify_document(physical_ir, style_catalog)
project_run_classification(run, paragraph_result)
project_target_classification(result)
```

`classify_document` deriva Normalized Text e Formatting Analysis internamente via APIs públicas congeladas da Analysis. A opção foi auditada e aceita: mesmas entradas → mesmos fatos; binding fica garantido por construção; não há parsing OOXML ad hoc.

### Projection

Somente resultados elegíveis projetam para `decision.TargetClassification`.

Provenance fechada:

```text
classification:direct
classification:inherited_from_paragraph
```

### E2E congelado

Sem `TargetClassification` manual:

```text
DOCX
-> Parser
-> Analysis
-> Classification(body)
-> TargetClassification
-> Decision P1–P4
```

Resultados auditados:
- bold true vs false -> non_compliant/deterministic_change;
- font 11pt vs 12pt -> non_compliant/deterministic_change;
- spacing 1.5 -> compliant/no_action;
- alignment both -> compliant/no_action.

Também:

```text
Heading1 -> heading level=1 -> projection paragraph/run
```

### Auditoria PR #6

Achados corrigidos antes do freeze:
1. **BLOQUEADOR:** parent/run binding ausente permitia herança de classe estrangeira;
2. **IMPORTANTE:** `basedOn` podia atravessar style-type boundary.

Foram adicionados testes adversariais para parent mismatch, prefix siblings, multi-hop basedOn, wrong-type hop e pStyle→character style.

Suíte final: **335/335**, com **290/290 regressões preservadas**.

### Dívidas registradas, não bloqueadoras

- `long_quote` executável;
- `reference` executável;
- ClassificationHints/localização de styles;
- `outlineLvl` factual;
- numeração estruturada;
- title/subtitle;
- short_quote/classes inline;
- LLM separado para abstentions;
- corpus real anotado de classificação;
- métricas por classe e thresholds somente após corpus.

## Fora do próximo ciclo

Continuam fora:
- OperationPlan;
- SafetyGate;
- XML patches;
- DOCX clean/review;
- UI/API web;
- long_quote/reference executáveis;
- expansão de Analysis sem necessidade comprovada.

## Próximo passo operacional

**Abrir uma nova etapa arquitetural pequena para decidir o próximo elo do pipeline, sem reabrir automaticamente Classification/Decision.**

Candidatos naturais agora:
1. `OperationPlan` — transformar `Decision` determinística em intenção operacional sem ainda tocar XML;
2. ou ampliar cobertura/classificação (`long_quote`/`reference`) apenas se houver evidência de que isso é mais prioritário para o MVP.

Antes de qualquer implementação do próximo elo: contrato primeiro, auditoria depois, código só então.
