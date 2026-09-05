# Decisão 0021 — Freeze Decision Layer v0.1

Status: **APPROVED / FROZEN**

## Escopo congelado

A Decision Layer v0.1 foi implementada, auditada adversarialmente, validada ponta a ponta e mergeada após o PR #5.

Pipeline congelado:

```text
Analysis View
+ TargetClassification explícita
+ regra validada / profile context
-> Decision Layer
```

A camada continua estritamente separada de classificação automática, OperationPlan, SafetyGate e patching.

## Vocabulário

Segue a decisão 0019, `decision_vocabulary_version = "0.1"`.

Primeiro vertical slice executável congelado:

```text
P1 / run / bold
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

`P1/run/italic` permanece congelado no vocabulário, mas fora deste primeiro slice executável.

## Modelos e API

Congelados:
- `DecisionKey`;
- `TargetClassification`;
- `DecisionContext`;
- `ProfileRef`;
- `RuleRef`;
- `FormattingRule`;
- `RuleMode`;
- `ComplianceStatus`;
- `Actionability`;
- `DecisionReason`;
- `DecisionTarget`;
- `EvidenceRef`;
- `Decision`;
- `LineSpacingValue`;
- `decide_property(...)`;
- `evaluate_target(...)`;
- registry versionado e `extract_resolved_value(...)`;
- serialização determinística.

## Dois eixos

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

`blocked` permanece fora da Decision Layer.

## Regras congeladas

### rule absent

```text
not_applicable / preserve / rule_absent
rule_ref = None
desired_value = None
```

Sem inferência de `aspect_id` ou `property_slot`; ambos vêm do `DecisionKey` explícito.

### containment

```text
not_evaluated / preserve / containment
rule_ref != None
desired_value = None
```

### Analysis status com regra ativa

```text
absent     -> unknown / review / analysis_absent
unresolved -> unknown / review / analysis_unresolved
invalid    -> unknown / review / analysis_invalid
ambiguous  -> unknown / review / analysis_ambiguous
```

`absent` nunca equivale a `false` ou a outro default implícito.

### exact

- match -> `compliant / no_action / matches_rule`;
- mismatch -> `non_compliant / deterministic_change / differs_from_rule` + `desired_value`.

### set

- allowed sem preferred -> `compliant / no_action / allowed_variant`;
- observed == preferred -> `compliant / no_action / matches_rule`;
- allowed mas != preferred -> `non_compliant / deterministic_change / preferred_variant_differs`;
- fora de allowed com preferred -> `non_compliant / deterministic_change / differs_from_rule`;
- fora de allowed sem preferred -> `non_compliant / human_choice / human_choice_required`.

## Invariante de desired_value

```text
desired_value != None
IFF
actionability == deterministic_change
```

O modelo rejeita estados inválidos diretamente.

## Comparação tipada

- bold: `bool`;
- font size: `Decimal` em pt, sem float;
- alignment: token canônico literal;
- spacing.line: `LineSpacingValue(rule, value, unit)` sem equivalência visual inferida.

## Fronteira com Analysis

O registry da decisão 0019 continua a única fronteira autorizada de mapping Analysis -> Decision Vocabulary.

Tipo de Analysis incompatível nessa fronteira deve falhar claramente; não há fallback nem inferência.

## Provenance

Decisões preservam:
- alvo físico (`structural_path + physical_hash`);
- `target_class` externo;
- aspect/slot;
- `profile_ref`;
- `rule_ref` quando houver regra concreta;
- snapshot de `winning_evidence` quando a decisão depende do valor documental.

`rule_absent` e `containment` podem manter `observed/evidence_ref=None` porque a razão não depende da observação.

## Determinismo e imutabilidade

Congelados:
- modelos frozen;
- sem mutação de Analysis/profile/classification;
- sem LLM runtime;
- sem relógio/random/locale implícito;
- serialização byte-estável;
- determinismo cross-process/hashseed;
- `evaluate_target` ordenado deterministicamente e restrito a um mesmo alvo físico/classificado.

## Auditoria PR #5

Base auditada:
`e83759decca053e8257ccc12b0758b98a10fcfd6`

Head final auditado:
`c340d1ab2c94b7c4af802419d0e414c4019be246`

Merge por squash:
`b81f628a0358cbc9483e9207d4f749ea4a2ca475`

A auditoria encontrou e corrigiu:
1. fronteira Analysis->Vocabulary retornando `AttributeError` cru para tipo de target incorreto;
2. ausência de teste E2E Analysis->Decision.

Correções finais:
- `_boundary_getattr` produz erro explícito de fronteira;
- E2E real com DOCX sintético -> parser -> Analysis formatting -> Decision.

## Testes

Suíte inicial do PR auditado: **288/288**.

Suíte final após correções: **290/290**.

Regressões congeladas anteriores: **267/267 preservadas**.

E2E congelado:

```text
DOCX sintético
-> DocxParser
-> StyleCatalog
-> resolve_run/paragraph_formatting
-> extract_resolved_value
-> evaluate_target
```

Cenário `body`:
- bold true vs regra false -> non_compliant/deterministic_change;
- font size 11pt vs 12pt -> non_compliant/deterministic_change;
- spacing 1.5 vs 1.5 -> compliant/no_action;
- alignment both vs both -> compliant/no_action.

## Fora deste freeze

- classificação acadêmica automática;
- italic executável na Decision Layer;
- demais slots P1–P9;
- P10–P27;
- regras cross-slot;
- agregador completo por documento;
- OperationPlan;
- SafetyGate;
- XML patches;
- DOCX clean/review;
- UI/API web.

## Reabertura

Reabrir apenas por falha de teste, impossibilidade técnica, contradição formal, mudança explícita de escopo ou novo risco de segurança.
