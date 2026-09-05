# 0024 — OperationPlan v0.1 Contract

Status: **APPROVED FOR IMPLEMENTATION**

## Contexto

O pipeline já congelado alcança:

```text
DOCX
-> Parser
-> Analysis
-> Classification
-> TargetClassification
-> Decision
```

O próximo estágio deve transformar somente decisões com `actionability == deterministic_change` em intenção operacional auditável, ainda sem SafetyGate, patching ou mutação de XML/DOCX.

Pipeline alvo:

```text
Decision
-> OperationPlan
-> SafetyGate
-> XML Patch
```

Princípio: **OperationPlan propõe; SafetyGate veta ou libera; patcher executa.**

## Fronteira

OperationPlan é puro, determinístico e sem IO.

NÃO:
- decide conformidade;
- escolhe variante normativa;
- reclassifica alvo;
- consulta Analysis/Classification para reinterpretar fatos;
- abre DOCX;
- lê OOXML;
- usa lxml/zipfile;
- gera patch;
- chama SafetyGate;
- altera XML/DOCX;
- usa rede/LLM/clock/random/locale.

Planner consome `Decision` congelada + referência explícita ao documento fonte.

## API v0.1

Unidade pura:

```text
plan_decision(decision: Decision) -> PlanningResult
```

Agregação:

```text
build_operation_plan(
    source_document: SourceDocumentRef,
    upstream_versions: UpstreamVersions,
    decisions: tuple[Decision, ...],
) -> OperationPlan
```

A agregação chama `plan_decision` internamente; não aceita `PlanningResult` externos como fonte de verdade.

## PlanningResult

Nunca retornar `None` para uma Decision válida.

```text
PlanningStatus:
    planned
    skipped
    unsupported
```

Semântica:
- `planned`: somente `deterministic_change` em slot suportado;
- `skipped`: `no_action | human_choice | review | preserve`;
- `unsupported`: `deterministic_change` em slot ainda fora do slice do planner.

`human_choice`, `review`, `preserve` e `no_action` são resultados legítimos, não exceções.

Exceção/fail-fast fica reservada a violação de contrato/invariante.

## Operation vocabulary

```text
OPERATION_PLAN_VERSION = "0.1"
OPERATION_VOCABULARY_VERSION = "0.1"
```

Primeiro e único kind executável:

```text
OperationKind.SET_PROPERTY
```

A operação reutiliza `DecisionKey`; não cria taxonomia paralela por slot.

Operações estruturais previstas em 0002 permanecem reservadas/documentadas, mas NÃO implementadas no slice 0.1.

## Slice executável

Somente:

```text
P1 / run / bold
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

`P1/italic` permanece fora do slice executável do planner.

## PlannedOperation

Modelo conceitual mínimo:

```text
PlannedOperation:
    kind: OperationKind
    key: DecisionKey
    target: OperationTarget
    precondition_observed
    desired_value
    decision_ref
```

Uma operação = uma intenção = no máximo uma mutação de propriedade.

Nenhuma operação implícita.

## OperationTarget

Copia fielmente da Decision:

```text
target_type
structural_path
physical_hash
target_class
aspect_id
property_slot
```

Invariantes:
- operation target == decision target;
- operation key == DecisionKey da Decision;
- nunca recalcular `target_class`;
- nunca trocar path/hash.

`physical_hash` é obrigatório e deverá ser verificado pelo SafetyGate/Patcher contra o alvo atual.

## Story/part no v0.1

`DecisionTarget` atual não carrega `story_id` nem `part`, e `structural_path` é relativo à story.

No slice executável atual, Classification só projeta alvos da story principal. Portanto o envelope v0.1 deve declarar explicitamente:

```text
planned_story_part = "word/document.xml"
```

Dívida futura: quando stories secundárias virarem executáveis, subir `story_id/part` de forma aditiva para `TargetClassification/DecisionTarget`.

## SourceDocumentRef

OperationPlan deve estar ancorado ao documento fonte agora, antes do SafetyGate.

Usar fingerprint já existente na PhysicalIR:

```text
SourceDocumentRef:
    package_sha256
    parser_version
```

`package_sha256` é hash dos bytes do DOCX/ZIP. Reempacotamento byte-diferente invalida o plano mesmo que semanticamente equivalente; isso é comportamento conservador e intencional.

## UpstreamVersions

No envelope, uma vez por plano:

```text
UpstreamVersions:
    analysis_formatting_version
    classification_version
    decision_version
    decision_vocabulary_version
```

Parser version fica em `SourceDocumentRef`.

## OperationPlan envelope

Modelo conceitual:

```text
OperationPlan:
    operation_plan_version
    operation_vocabulary_version
    source_document
    planned_story_part
    upstream_versions
    source_decisions_hash
    operations
```

Plano vazio (`operations=()`) é válido.

## Decision provenance

Cada operação carrega:

```text
decision_ref = sha256(serialize_decision(decision))
```

Sem UUID/random.

Não duplicar `profile_ref`/`rule_ref` como fonte paralela na operação; permanecem recuperáveis na Decision original identificada por `decision_ref`.

O plano também carrega:

```text
source_decisions_hash
```

derivado deterministicamente do conjunto ordenado de Decisions serializadas, fechando a cadeia plano↔decisões.

Não congelar `operation_id` nem `plan_id` no v0.1; podem ser derivados quando TransformLog tiver consumidor real.

## Compare-and-set semântico

Para `SET_PROPERTY`, `precondition_observed` é **obrigatória** e vem diretamente de `decision.observed`.

Conceito:

```text
se o valor semântico atual ainda for o observado,
propor desired_value
```

Isso implementa o `before/after` previsto em 0002 e protege contra target drift semântico entre decisão e aplicação.

Invariantes:

```text
precondition_observed is not None
desired_value is not None
precondition_observed != desired_value
```

`deterministic_change` a partir de Analysis `absent` não existe no v0.1; não implementar set-from-absent.

SafetyGate futuro deve re-resolver o estado atual e comparar semanticamente a precondition antes de liberar.

## Value model

OperationPlan permanece em valores semânticos, nunca OOXML.

### bold

```text
bool
```

### font_size

Decision guarda `Decimal` depois de validar `pt` upstream. Planner deve materializar valor tipado com unidade explícita:

```text
LengthValue(value=Decimal(...), unit="pt")
```

Não converter para half-points.

### alignment

Token canônico literal (`"both"`, etc.), sem label de UI.

### spacing.line

Reutilizar o tipo público imutável `LineSpacingValue(rule, value, unit)` da Decision.

Planner não importa `ResolvedValue`, `Length` ou `LineSpacing` da Analysis.

## Autoridade do actionability

Planner não hardcode reason para decidir se há mutação; `actionability` é a autoridade.

Ainda assim, deve fail-fast em combinações internamente contraditórias do objeto Decision.

Para `deterministic_change`, exigir também:
- `desired_value != None`;
- `observed != None`;
- `rule_ref != None`;
- slot suportado e target_type compatível;
- versions compatíveis;
- anchor completo.

## Estados não operacionais

### no_action
`skipped`; nenhuma operação.

### human_choice
`skipped`; planner nunca escolhe alternativa.

### review
`skipped`; planner não resolve Analysis incerta.

### preserve
`skipped`; nenhuma operação ou placeholder mutável.

Containment permanece efetivamente NÃO TOCAR; seu rastro fica no PlanningResult/Decision para relatório.

## Unsupported deterministic slot

Se chegar `deterministic_change` em slot conhecido mas não suportado pelo planner v0.1:

```text
PlanningStatus.UNSUPPORTED
```

Nunca retornar silenciosamente `None` ou tratá-lo como `no_action`.

## Agregação

`build_operation_plan` recebe Decisions possivelmente de múltiplos alvos do mesmo documento.

### conflito
Mesmo target + mesma key + desired diferentes:
- falha de agregação;
- planner nunca escolhe uma por ordem.

### duplicata idêntica
Mesmo target + mesma key + mesmo desired:
- também falha de agregação no v0.1;
- não deduplicar silenciosamente.

Ambos indicam bug upstream.

## Ordenação

Plano usa ordem total determinística para serialização, por exemplo:

```text
(planned_story_part, structural_path, physical_hash, aspect_id, property_slot)
```

Esta ordem NÃO é declarada como ordem documental nem ordem futura de aplicação. `structural_path` lexicográfico não representa corretamente índices como `p[10]` vs `p[2]`; isso é inócuo no v0.1 porque `SET_PROPERTY` é comutativo e a ordenação serve somente para determinismo de bytes.

Operações estruturais futuras exigirão regra própria de aplicação/re-endereçamento.

## Falha parcial

Estados legítimos `skipped/unsupported` não impedem planejamento de outras Decisions.

Exemplo:
- bold deterministic -> planned;
- font deterministic -> planned;
- spacing no_action -> skipped;
- alignment review -> skipped.

Conflito/duplicidade estrutural de operações é diferente: invalida a agregação porque compromete a confiabilidade do plano.

## SafetyGate

OperationPlan NÃO carrega:
- safe=true;
- gate_passed;
- blocked;
- operation_class de segurança.

No v0.1, `(OperationKind, target_type, property_slot)` fornece natureza factual suficiente para o futuro gate.

SafetyGate deverá, no mínimo, poder verificar:
- package fingerprint;
- target `physical_hash`;
- precondition semântica atual;
- regra/aspecto via cadeia de provenance da Decision;
- suporte seguro do applicator.

## Stale-plan protection

O plano deve carregar três níveis de proteção:
1. `package_sha256` — documento/pacote;
2. `physical_hash` — alvo físico;
3. `precondition_observed` — estado semântico.

OperationPlan apenas preserva essas precondições; SafetyGate/Patcher fará a verificação atual.

## Serialização e determinismo

- dataclasses/modelos frozen;
- tuples, não listas mutáveis públicas;
- enums serializados como strings;
- Decimal serializado como string;
- `sort_keys=True`;
- separadores canônicos;
- UTF-8;
- sem timestamp;
- sem random/hash-order dependency;
- mesmo input -> mesmos bytes em processo/subprocess/hashseed.

## Fora do v0.1

- SafetyGate;
- TransformLog;
- patch/applicator;
- half-points/twips/OOXML payload;
- MOVE_BLOCK/INSERT_BLOCK/MERGE_BLOCKS executáveis;
- operation/plan UUIDs;
- set-from-absent;
- stories secundárias executáveis;
- original_index para ordenação estrutural;
- P5–P27.

## Primeiro vertical slice de implementação

Deve provar:

```text
DOCX
-> Parser
-> Analysis
-> Classification
-> Decision
-> OperationPlan
```

Cenário body esperado:
- bold true vs false -> `planned SET_PROPERTY`, precondition true, desired false;
- font 11 vs 12 -> `planned SET_PROPERTY`, precondition 11pt, desired 12pt;
- spacing correto -> `skipped/no_action`;
- alignment correto -> `skipped/no_action`.

Sem SafetyGate e sem XML.

## Testes mínimos futuros

1. bold mismatch -> operação;
2. font mismatch -> operação tipada pt;
3. spacing match -> skipped/no_action;
4. alignment match -> skipped/no_action;
5. human_choice -> skipped;
6. review -> skipped;
7. preserve -> skipped;
8. precondition observada preservada;
9. observed == desired em deterministic_change -> contrato inválido;
10. package_sha256 presente;
11. physical_hash preservado;
12. source_decisions_hash muda se decisão muda;
13. duplicate idêntica -> erro;
14. conflito same target/key -> erro;
15. ordenação determinística;
16. unsupported deterministic slot -> fail-visible;
17. empty plan válido;
18. serialização cross-process/hashseed;
19. inputs não mutados;
20. E2E completo até OperationPlan.

## Dívidas não bloqueadoras

1. `story_id/part/original_index` não estão em `DecisionTarget`; v0.1 cobre story principal via envelope. Subir aditivamente antes de executar stories secundárias.
2. `original_index` será necessário quando operações estruturais exigirem ordem real do documento.
3. `package_sha256` byte-level invalida reempacotamento semanticamente equivalente; conservador por design.
4. ordenação lexicográfica de `structural_path` não é ordem documental; serve só para bytes determinísticos no slice atual.

## Reabertura

Este contrato só deve ser reaberto por:
- teste que revele contradição;
- impossibilidade técnica;
- conflito com camada congelada;
- mudança explícita de escopo;
- novo risco de segurança.

## Próximo passo

Implementar OperationPlan v0.1 em branch própria, preservando integralmente os 335 testes congelados atuais, e submeter a auditoria adversarial antes de merge/freeze.
