# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a/v0.1b congeladas; Decision Vocabulary v0.1 congelado; Decision Layer v0.1 congelada em 0021; **Classification Layer v0.1 contratada em 0022 e pronta para implementação do primeiro slice.**

Validação corrente:
- parser v0.4: **102/102**;
- parser + Analysis v0.1a: **154/154**;
- Analysis até v0.1b Marco 1: **222/222**;
- Analysis completa: **267/267**;
- após Decision Layer v0.1: **290/290**;
- failures: 0;
- errors: 0;
- skips: 0.

PRs/freeze principais:
- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1; head auditado `c340d1ab2c94b7c4af802419d0e414c4019be246`; squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021.

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

Marco 1 congelado:
- run: `w:sz`, `w:rFonts` 8 slots, `w:lang` 3 slots, `w:u`, `w:vertAlign`;
- paragraph: `pStyle`, `w:jc`, `w:spacing`, `w:ind` com cláusula numbering↔indent;
- regras de defaults/styleId conforme 0016.

Marco 2 congelado:
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
+ TargetClassification explícita
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

E2E congelado:

```text
DOCX
-> Parser
-> Analysis
-> Decision
```

com classificação `body` ainda fornecida manualmente.

Suíte final Decision: **290/290**.

## Classification Layer v0.1 — 0022

Status: **APPROVED FOR IMPLEMENTATION**.

Pipeline:

```text
PhysicalIR
+ Normalized Text
+ Formatting Analysis / StyleCatalog
+ contexto estrutural/sequencial
-> ClassificationResult
-> projeção segura para TargetClassification
-> Decision Layer
```

### Fronteira

Classification NÃO:
- decide conformidade;
- consulta perfil normativo como verdade classificatória;
- gera desired_value;
- cria OperationPlan;
- chama SafetyGate;
- altera DOCX/XML;
- lê OOXML cru por conta própria;
- usa LLM/probabilidade/random/clock/locale na v0.1.

### Unidade e taxonomia

Parágrafo é unidade primária.

Vocabulário v0.1:

```text
body
heading
long_quote
reference
```

`unknown` NÃO é classe.

`heading` usa `metadata.level = int | None`, não classes `heading_N`.

`reference` = entrada individual; cabeçalho da seção = heading.

Runs recebem classe apenas por projeção explícita do parágrafo pai.

### Status

```text
classified
abstained
not_applicable
```

`ambiguous` é reason de abstention (`conflicting_evidence`), não status.

Invariante:

```text
status == classified  IFF  target_class is not None
```

Abstained/not_applicable nunca projetam para TargetClassification.

### Basis / elegibilidade

```text
explicit
structural
heuristic
```

Elegibilidade automática é derivada, não um campo separado:

```text
status == classified
AND basis in {explicit, structural}
```

Sem confidence numérica.

### Evidence

`ClassificationEvidence` registra fatos com:
- source_kind;
- source_ref;
- feature;
- observed_value;
- polarity (`supports|contradicts`);
- strength (`explicit|structural|weak`).

Aparência (bold, font size, center, indent, uppercase, texto curto) é weak e NÃO classifica sozinha.

### Style identity map

`classification_style_identity_version = "0.1"`.

Mapa versionado pertence à Classification Layer e usa identidade documental verificável, não matching ad hoc de nome.

Primeiro slice:
- identidades HeadingN verificáveis -> `heading`, level N;
- Normal/BodyText verificáveis -> `body` quando contexto permitido;
- custom style pode herdar classe via cadeia basedOn verificável;
- nome custom/localizado semelhante a heading/body NÃO classifica sozinho;
- futura localização/renomeação exigirá `ClassificationHints` próprio, versionado e separado do perfil normativo.

### Body

Nunca fallback residual.

Exige evidência positiva de identidade + contexto permitido.

### Heading

Exige identidade reconhecida no slice 1.

Formatação direta parecida com heading não classifica.

### Long quote / Reference

Estão no vocabulário, mas fora do primeiro slice executável.

Ativação futura depende de evidência mínima formal + corpus anotado.

### Context policies do slice 1

- story principal apenas;
- secondary stories -> not_applicable/unsupported_story;
- tabelas/células/block containers -> abstained/unsupported_context;
- numbering warning -> abstained/unsupported_context;
- empty paragraph -> abstained/empty_content;
- nenhum fallback por vizinhança.

### Reasons fechados

Classificação:
```text
explicit_style_signal
structural_context_signal
inherited_from_paragraph
```

Abstenção:
```text
insufficient_evidence
conflicting_evidence
empty_content
unsupported_context
```

Não aplicabilidade:
```text
unsupported_story
unsupported_target
parent_not_classified
```

Prioridade determinística:
1. unsupported_story / unsupported_target;
2. parent_not_classified;
3. empty_content;
4. unsupported_context;
5. conflicting_evidence;
6. insufficient_evidence;
7. razões positivas.

### Provenance

Modelo rico:
```text
direct
inherited_from_paragraph
```

TargetClassification projetada usa strings fechadas:
```text
classification:direct
classification:inherited_from_paragraph
```

parent anchor completo permanece no modelo rico.

### API prevista

```text
classify_document(...)
project_run_classification(...)
project_target_classification(...)
```

API pública primária é por documento/story, não paragraph isolado.

### Analysis debts registradas, não bloqueadoras

- `w:outlineLvl` ainda não exposto;
- numeração estruturada ainda não exposta, apenas warning;
- hints para style names localizados/renomeados ainda inexistentes.

Regra: se fato físico faltar, expandir Analysis factual antes; classifier não lê OOXML cru.

### Primeiro vertical slice a implementar

```text
body
heading
abstain
```

Deve provar:
- discriminação entre duas classes;
- abstention segura;
- ausência de fallback;
- heading level metadata;
- paragraph→run inheritance;
- projeção segura para TargetClassification;
- E2E completo sem fixture manual de target_class.

E2E-alvo:

```text
DOCX
-> Parser
-> Analysis
-> Classification(body)
-> TargetClassification
-> Decision P1–P4
```

### Fixtures obrigatórias mínimas

1. Normal/body identity reconhecida -> body;
2. Heading1 -> heading level 1;
3. custom style basedOn Heading1 -> heading;
4. formatação direta parecida com heading sem identidade -> abstain;
5. vazio -> abstain;
6. tabela com body style -> abstain;
7. numbering warning -> abstain;
8. run herdado de body -> inherited_from_paragraph + parent anchor;
9. custom style com nome semelhante sem basedOn -> abstain;
10. referências continuam sem ativação automática no slice 1.

### Corpus e métricas

Criar corpus de classificação separado do corpus-base de formatação após o contrato/slice sintético.

Freeze futuro deve reportar:
- precision por classe;
- false-positive rate por classe;
- coverage;
- abstention rate.

Não usar accuracy isolada.

Nenhum threshold de produção antes de corpus anotado.

Versionamento:

```text
CLASSIFICATION_VERSION = "0.1"
CLASSIFICATION_VOCABULARY_VERSION = "0.1"
classification_style_identity_version = "0.1"
```

## Fora do próximo ciclo

Continuam fora:
- long_quote executável;
- reference executável;
- title/subtitle;
- short_quote e classes inline;
- ClassificationHints/localização de styles;
- outlineLvl/numeração estruturada na Analysis;
- LLM classifier;
- OperationPlan;
- SafetyGate;
- patching;
- DOCX clean/review;
- UI/API web.

## Próximo passo operacional

**Implementar o primeiro vertical slice da Classification Layer v0.1 (`body + heading + abstain`) em branch própria.**

Antes de merge/freeze:
1. preservar integralmente os **290 testes congelados**;
2. implementar modelos frozen + style identity map + contexto mínimo + projeção paragraph→run;
3. testar nenhum fallback para body;
4. testar custom styles adversariais;
5. adicionar E2E `DOCX → Parser → Analysis → Classification → Decision` sem target_class manual;
6. rodar determinismo cross-process/hashseed;
7. auditoria adversarial Kimi;
8. só depois merge + decisão de freeze + atualização deste HANDOFF.
