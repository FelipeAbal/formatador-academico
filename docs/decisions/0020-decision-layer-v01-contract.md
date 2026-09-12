# Decisão 0020 — Decision Layer v0.1 Contract

Status: **APPROVED FOR IMPLEMENTATION**

## Objetivo

Definir a camada determinística que transforma:

```text
Analysis View + TargetClassification + ValidatedProfile -> Decision
```

A Decision Layer julga conformidade e acionabilidade. Ela NÃO classifica alvos, NÃO produz `OperationPlan`, NÃO chama SafetyGate e NÃO altera XML/DOCX.

Pipeline:

```text
Analysis View
-> TargetClassification
-> ValidatedProfile
-> Decision Layer
-> OperationPlan
-> SafetyGate
-> XML patches
```

## Inputs obrigatórios

1. Analysis View congelada (`ResolvedRunFormatting` / `ResolvedParagraphFormatting`);
2. `TargetClassification` externo, serializável e versionado;
3. `ValidatedProfile` previamente validado;
4. `decision_vocabulary_version = "0.1"` conforme decisão 0019.

A Decision Layer não aceita perfil estruturalmente inválido como caso normal de runtime.

## TargetClassification

A classificação acadêmica é externa à Decision Layer. A camada recebe `target_class` já determinado. No primeiro vertical slice, classificações explícitas em fixtures são suficientes.

A Decision Layer nunca decide se um parágrafo é corpo, título, citação longa, referência etc.

## Unidade mínima de decisão

Uma decisão por:

```text
(target, aspect_id, property_slot)
```

com `DecisionTarget` contendo:
- `target_type`;
- `physical_anchor` (`structural_path + physical_hash`);
- `target_class`;
- `aspect_id`;
- `property_slot`.

Specs compostos são avaliados por slot; não existe decisão agregada de `FontSpec`, `SpacingSpec` ou `IndentSpec` inteiro.

## Dois eixos independentes

### ComplianceStatus

Conjunto fechado:

```text
compliant
non_compliant
unknown
not_applicable
not_evaluated
```

### Actionability

Conjunto fechado:

```text
no_action
deterministic_change
human_choice
review
preserve
```

Não usar enum único. Conformidade e acionabilidade são fatos independentes.

`blocked` NÃO pertence à Decision Layer; veto de execução é responsabilidade futura do SafetyGate.

## Rule model mínimo

Estrutura única e tipada:

```text
FormattingRule:
    rule_id
    aspect_id
    property_slot
    mode              # exact | set | containment
    expected          # mode=exact
    allowed           # mode=set
    preferred         # opcional, mode=set
```

Sem linguagem genérica de regras, expressões ou condicionais na v0.1.

`PresenceRule`/`AbsenceRule` ficam fora da v0.1.

### Validação prévia do perfil

`ValidatedProfile` é pré-condição. Antes da Decision Layer devem ser rejeitados, por exemplo:
- aspect/slot desconhecido;
- valor fora do vocabulário;
- `preferred` fora de `allowed`;
- unidade incompatível com o slot;
- estrutura inconsistente.

A Decision Layer não cria `RuleStatus.INVALID`.

## Rule provenance

```text
RuleRef:
    profile_id
    profile_version
    rule_id
    aspect_id
    path
```

`rule_ref` existe somente quando há uma regra concreta.

Se regra está ausente:

```text
rule_ref = None
```

A decisão ainda carrega `profile_ref`, `aspect_id` e `property_slot`, sem fabricar provenance de regra inexistente.

Em `containment`, a regra existe; logo `rule_ref` é preenchido normalmente.

## Decision model mínimo

Modelo técnico, frozen, serializável e determinístico:

```text
Decision:
    decision_version
    decision_vocabulary_version
    target
    compliance
    actionability
    reason
    analysis_status
    observed
    desired_value
    profile_ref
    rule_ref
    evidence_ref
    decision_warnings
```

### desired_value

`desired_value` pertence à Decision Layer como valor semântico declarativo, não operação física.

Invariante:

```text
desired_value != None
IFF actionability == deterministic_change
```

Exemplo:

```text
observed = 11pt
desired_value = 12pt
```

Sem XPath, sem XML e sem operação de patch.

Não criar `automatic_candidate`: é redundante com `actionability`.

## Provenance / evidence

Toda decisão deve ser rastreável ao:
- alvo físico;
- classificação usada;
- aspecto/slot;
- perfil consultado;
- regra concreta, quando existir;
- evidence da Analysis utilizada.

Para decisões baseadas em uma propriedade resolvida, `evidence_ref` pode copiar `winning_evidence` e manter o `physical_anchor` como referência da Analysis completa. Não carregar grafo mutável vivo.

Para `rule_absent`/`containment`, `evidence_ref` pode ser `None` se a razão não depender de observar valor documental.

## Reason codes fechados

```text
matches_rule
differs_from_rule
allowed_variant
preferred_variant_differs
human_choice_required
rule_absent
containment
analysis_absent
analysis_unresolved
analysis_invalid
analysis_ambiguous
not_applicable
```

Mensagens livres não são semântica.

`non_compliant` é resultado normal e NÃO é warning.

Warnings são reservados para anomalias de contrato/execução da Decision Layer, não para mera divergência com perfil.

## Matriz principal

### Regra ausente

Para qualquer Analysis status:

```text
compliance = not_applicable
actionability = preserve
reason = rule_absent
rule_ref = None
warning = nenhum
```

### Contenção

Para qualquer Analysis status:

```text
compliance = not_evaluated
actionability = preserve
reason = containment
warning = nenhum
```

Princípio: contenção = NÃO TOCAR + NÃO SINALIZAR.

### Regra ativa + Analysis resolved

#### exact

- match -> `compliant / no_action / matches_rule`
- mismatch -> `non_compliant / deterministic_change / differs_from_rule`, com `desired_value=expected`

#### set com preferred

- observado == preferred -> `compliant / no_action`
- observado em allowed mas != preferred -> `non_compliant / deterministic_change / preferred_variant_differs`, `desired_value=preferred`
- observado fora de allowed -> `non_compliant / deterministic_change`, `desired_value=preferred`

#### set sem preferred

- observado em allowed -> `compliant / no_action / allowed_variant`
- observado fora de allowed -> `non_compliant / human_choice / human_choice_required`, `desired_value=None`

## Analysis status -> Decision

Com regra ativa:

```text
unresolved -> unknown / review / analysis_unresolved
invalid    -> unknown / review / analysis_invalid
ambiguous  -> unknown / review / analysis_ambiguous
```

Nunca converter esses estados automaticamente em `needs_change`/`deterministic_change`.

### Política para absent

`absent` permanece distinto de `resolved false` ou qualquer default implícito.

Na v0.1, para todos os slots inicialmente suportados:

```text
analysis = absent + regra ativa
-> compliance = unknown
-> actionability = review
-> reason = analysis_absent
```

A Decision Layer v0.1 NÃO assume categoria de "ausência segura". Tal categoria nasce vazia e só pode crescer por decisão formal futura.

Isso vale especialmente para toggles: `bold=absent` não equivale a `bold=false`.

## Comparação tipada

Não usar string comparison ingênua.

- `Decimal` para grandezas;
- `bool` para toggles;
- token documental para enums OOXML já expostos pela Analysis;
- comparação por slot para specs compostos;
- incompatibilidade de unidade deve ser rejeitada na validação do perfil, não resolvida por heurística na Decision Layer.

## Falha parcial

Uma decisão não derruba as demais.

Exemplo:

```text
font_size -> non_compliant / deterministic_change
bold      -> compliant / no_action
alignment -> unknown / review
```

Target continua produzindo as outras decisões normalmente.

## Determinismo

A Decision Layer é 100% determinística:
- sem LLM runtime;
- sem relógio;
- sem locale implícito;
- sem random;
- sem ordem dependente de hash/dict/set;
- serialização estável;
- outputs frozen;
- sem mutação de Analysis, classificação ou profile.

Ordenação agregada futura deve usar chave total determinística, por exemplo:

```text
(physical_anchor, aspect_id, property_slot)
```

## API mínima

Primeiro nível:

```text
decide_property(rule_or_none, resolved_value, target_context) -> Decision
```

Segundo nível:

```text
evaluate_target(...) -> tuple[Decision, ...]
```

Agregador por documento fica para etapa posterior.

## Decision Vocabulary v0.1

Conforme decisão 0019:

```text
P1 / run / bold
P1 / run / italic
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

A tabela versionada de mapeamento `property_slot -> Analysis source` é a fronteira autorizada entre Decision Layer e Analysis View.

## Primeiro vertical slice de implementação

Implementar somente quatro propriedades:

```text
P1 / run / bold
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

`P1/italic` está congelado no vocabulário, mas pode ficar fora do primeiro slice executável sem breaking change.

Classificação explícita/manual em fixtures.

Esse slice prova:
- bool/toggle;
- Decimal;
- token documental;
- spec composto por slot;
- match/mismatch;
- `absent` conservador;
- provenance;
- determinismo;
- falha parcial.

## Fora do primeiro slice

- `italic` se não necessário ao slice inicial;
- underline;
- FontSpec family slots;
- LanguageSpec;
- spacing before/after;
- indents;
- P5–P9;
- regras cross-slot de destaque;
- classificação acadêmica automática;
- referências/citações;
- OperationPlan;
- SafetyGate;
- patches;
- DOCX clean/review;
- UI/API web.

## Limitação cross-slot conhecida

Regras do tipo:

```text
allowed = [bold, italic]
```

que expressam escolha entre propriedades distintas NÃO são representadas pelo rule model por slot da v0.1.

Esse caso exigirá futura extensão cross-slot de regra/aspecto, sem alterar a semântica dos slots `P1/bold` e `P1/italic` já congelados.

## Testes mínimos obrigatórios para implementação

1. exact match;
2. exact mismatch + desired_value;
3. rule absent -> preserve silencioso + rule_ref None;
4. containment -> preserve silencioso + rule_ref presente;
5. set allowed observado;
6. set + preferred observado não preferred;
7. set sem preferred observado fora -> human_choice_required;
8. resolved;
9. absent -> unknown/review;
10. unresolved -> unknown/review;
11. invalid -> unknown/review;
12. ambiguous -> unknown/review;
13. provenance target/profile/rule/evidence;
14. falha parcial com resultados diferentes no mesmo target;
15. determinismo same-process;
16. determinismo cross-process/hashseed;
17. inputs não mutados;
18. serialização byte-estável;
19. ordenação determinística do `evaluate_target`;
20. `desired_value` ausente em human_choice/review/preserve/no_action.

## Reabertura

Reabrir apenas por:
- falha de teste;
- impossibilidade técnica;
- contradição normativa/arquitetural nova;
- mudança explícita de escopo;
- novo risco de segurança.
