# HANDOFF — Formatador Acadêmico

## Estado atual

**Fase:** corpus-base v1 congelado; parser físico v0.4 congelado; Analysis View v0.1a e v0.1b congeladas; Decision Vocabulary v0.1 congelado (0019); **Decision Layer v0.1 — primeiro vertical slice implementado, auditado, mergeado e congelado pela decisão 0021.**

Validação corrente:
- parser v0.4: **102/102**;
- baseline parser + v0.1a: **154/154**;
- após Marco 1 v0.1b: **222/222**;
- após Marco 2 v0.1b: **267/267**;
- após Decision Layer v0.1: **290/290**;
- failures: 0;
- errors: 0;
- skips: 0.

PRs principais:
- PR #3 — Analysis v0.1b Marco 1; freeze 0017;
- PR #4 — Analysis v0.1b Marco 2; freeze 0018;
- PR #5 — Decision Layer v0.1 primeiro vertical slice; head final auditado `c340d1ab2c94b7c4af802419d0e414c4019be246`; merge por squash `b81f628a0358cbc9483e9207d4f749ea4a2ca475`; freeze 0021.

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

Para trabalho com Kimi:
- mesmo projeto;
- novo chat por etapa técnica grande;
- no início: HANDOFF + SHA exato do `main` + tarefa fechada;
- implementação só conta com branch/commit/PR real ou diff completo;
- estado do GitHub prevalece sobre sandbox/conversa;
- auditoria adversarial antes de merge/freeze.

## Objetivo do MVP

Formatar com segurança DOCX acadêmicos existentes a partir de perfil formal explicitamente declarado. Não promete conformidade ABNT genérica.

Saídas:
1. DOCX limpo;
2. DOCX de revisão;
3. relatório.

Princípio: **Na dúvida, marcar.**

## Segurança

- nenhuma invenção/perda substantiva;
- só atuar em subaspecto autorizado;
- ambiguidade não é resolvida silenciosamente;
- opacos são preservados/protegidos;
- Safety Gate é veto, nunca autorização;
- C3 exige revisão humana.

## Corpus congelado v1

- 41 fixtures;
- baseline motor nulo: 20/41 = 48,8%;
- precisão-alvo automática >=99%;
- alto risco desejado >=99,5%;
- tolerância zero a invenção/perda conhecida, dano a campo e alteração indevida de citação direta.

## Physical layer / parser — 0001–0012

Congelado:
- OriginalPackage imutável;
- PhysicalIR derivada, serializável e forense;
- OOXML+lxml autoritativo;
- saída nunca reconstruída da IR;
- children[] autoritativo;
- stories secundárias, parse parcial, tabelas, nested tables e block containers;
- parser v0.4.0 congelado em 0012;
- suíte parser: **102/102**.

## Analysis View v0.1a — 0013–0014

Congelada:
- um segmento por fragmento físico;
- segments[] autoritativo;
- default_text derivado;
- offsets em code points Python;
- zero-width para não participantes;
- opacos preservados;
- sem falsa precisão em breaks;
- serialização determinística;
- sem lxml vivo;
- PhysicalIR imutável.

## Analysis View v0.1b — 0015–0018

### Marco 1 — freeze 0017

Run:
- w:sz;
- w:rFonts 8 slots;
- w:lang 3 slots;
- w:u;
- w:vertAlign.

Paragraph:
- pStyle;
- w:jc;
- w:spacing;
- w:ind com cláusula numbering↔indent.

Regras normativas de 0016:
- multiple defaults: última ocorrência documental vence + warning;
- duplicate styleId: primeira ocorrência é referencial + warning;
- styleId ausente = None;
- style sem ID pode ser default;
- w:type ausente => paragraph;
- essas anomalias não geram ambiguous.

### Marco 2 — freeze 0018

Congelados w:b e w:i.

Styles/docDefaults:
`docDefaults -> paragraph root→specific -> character root→specific`

- omitido/1/true/on => toggle;
- 0/false/off => no-op;
- lexical inválido, inclusive w:val="", => invalid.

Direct formatting:
- omitido/1/true/on => true absoluto;
- 0/false/off => false absoluto;
- direct é terminal e nunca participa da paridade.

Outros invariantes:
- tudo ausente => absent, nunca resolved false;
- duplicate semanticamente idêntico => aplica uma vez + warning;
- duplicate conflitante => ambiguous;
- cycle relevante sem direct => unresolved(style_cycle);
- direct terminal pode resolver apesar de cycle inferior;
- evidence em ordem real de composição;
- multi-evidence não recebe falsa causalidade em winning_evidence.

Suíte final Analysis: **267/267**.

## Decision Vocabulary v0.1 — 0019

`decision_vocabulary_version = "0.1"`

DecisionKey:
`(target_type, aspect_id, property_slot)`

Vocabulário congelado:

```text
P1 / run / bold
P1 / run / italic
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

Regras:
- physical_anchor pertence ao DecisionTarget;
- target_class é classificação externa;
- sem nomes OOXML na API pública;
- registry versionado é a fronteira única Analysis -> Decision Vocabulary;
- P5–P9 permanecem macro;
- regras cross-slot de destaque ficam fora da v0.1.

## Decision Layer v0.1 — 0020 + freeze 0021

Pipeline congelado:

```text
Analysis View
+ TargetClassification explícita
+ regra/profile context validados
-> Decision Layer
```

A camada NÃO:
- classifica academicamente;
- usa LLM runtime;
- cria OperationPlan;
- chama SafetyGate;
- gera patch;
- altera XML/DOCX.

### Primeiro vertical slice executável congelado

```text
P1 / run / bold
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

`P1/italic` permanece no vocabulário, mas fora do slice executável.

### Dois eixos

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

`blocked` pertence ao SafetyGate futuro.

### Estados seguros

Rule absent:
`not_applicable / preserve / rule_absent`, `rule_ref=None`, sem inferência de aspect/slot.

Containment:
`not_evaluated / preserve / containment`, regra concreta e `rule_ref` presente.

Regra ativa:
- absent -> unknown/review/analysis_absent;
- unresolved -> unknown/review/analysis_unresolved;
- invalid -> unknown/review/analysis_invalid;
- ambiguous -> unknown/review/analysis_ambiguous.

Nunca tratar absent como false/default implícito.

### Exact/set

Exact:
- match -> compliant/no_action;
- mismatch -> non_compliant/deterministic_change + desired_value.

Set:
- allowed sem preferred -> compliant/no_action/allowed_variant;
- observed == preferred -> compliant/no_action/matches_rule;
- allowed mas != preferred -> non_compliant/deterministic_change/preferred_variant_differs;
- fora de allowed com preferred -> non_compliant/deterministic_change/differs_from_rule;
- fora de allowed sem preferred -> non_compliant/human_choice/human_choice_required.

Invariante:

```text
desired_value != None
IFF
actionability == deterministic_change
```

### Comparação tipada

- bold: bool;
- font_size: Decimal pt;
- alignment: token canônico literal;
- spacing.line: LineSpacingValue(rule, value, unit), sem equivalência visual inferida.

### Provenance

Decision preserva:
- structural_path + physical_hash;
- target_class;
- aspect/slot;
- profile_ref;
- rule_ref quando houver regra;
- EvidenceRef snapshot quando necessário.

### Determinismo

- modelos frozen;
- inputs não mutados;
- sem random/clock/locale/LLM;
- serialização byte-estável;
- cross-process/hashseed determinístico;
- evaluate_target ordenado deterministicamente e restrito ao mesmo alvo físico/classificado.

### Auditoria PR #5

Encontrou/corrigiu:
1. tipo de target incorreto na fronteira Analysis→Vocabulary antes retornava AttributeError cru; agora falha com TypeError explícito;
2. faltava E2E Analysis→Decision; adicionado.

Suíte final: **290/290**, com **267/267 regressões preservadas**.

E2E congelado:

```text
DOCX sintético
-> DocxParser
-> StyleCatalog
-> resolve_run/paragraph_formatting
-> extract_resolved_value
-> evaluate_target
```

Cenário body:
- bold true vs false -> non_compliant/deterministic_change;
- font_size 11pt vs 12pt -> non_compliant/deterministic_change;
- spacing 1.5 vs 1.5 -> compliant/no_action;
- alignment both vs both -> compliant/no_action.

## Fora do próximo ciclo

Continuam fora:
- classifier acadêmico automático;
- italic executável na Decision Layer;
- demais slots P1–P9;
- P10–P27;
- regras cross-slot;
- OperationPlan;
- SafetyGate;
- XML patches;
- DOCX clean/review;
- UI/API web.

## Próximo passo operacional

**Abrir o contrato da Classification Layer / TargetClassification producer, ainda sem código.**

Objetivo da próxima etapa: definir como um alvo da Analysis recebe classes como `body`, `heading`, `long_quote`, `reference` etc. sem contaminar parser, Analysis ou Decision Layer.

Primeiro ciclo deve ser arquitetural e pequeno:
1. definir taxonomia mínima de classes necessária ao MVP;
2. definir provenance/confidence/abstenção;
3. separar classificação determinística de heurística/C2/C3;
4. permitir classificação manual em fixtures como baseline;
5. decidir quando a classificação pode ser automática e quando deve exigir review;
6. não implementar OperationPlan/SafetyGate/patching antes desse contrato ser auditado.
