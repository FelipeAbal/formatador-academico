# 0025 — Freeze OperationPlan v0.1

Status: FROZEN
Date: 2026-09-05

## Context

Decision 0024 defined the OperationPlan v0.1 contract as the deterministic bridge from frozen Decision outputs to non-executed operational intent, before SafetyGate and before any XML patch.

PR #7 implemented the first vertical slice and was adversarially audited before merge.

Final audited branch head:

`871e4a5cc379bbb2b2e04504a871188366718092`

Squash merge commit:

`1c11d08dcd6fc219bb2f4e0ce5321db027a5801a`

Final audited suite:

- total: 389
- passes: 389
- failures: 0
- errors: 0
- skips: 0
- previous frozen regressions preserved: 335/335
- new OperationPlan tests: 54

## Frozen pipeline boundary

```text
Decision
-> PlanningResult
-> OperationPlan
-> future SafetyGate
-> future XML patch
```

OperationPlan proposes deterministic semantic operations. It does not decide safety, mutate XML, open DOCX files, re-run Analysis, reinterpret Classification, or execute patches.

## Frozen executable vocabulary

```text
OPERATION_PLAN_VERSION = "0.1"
OPERATION_VOCABULARY_VERSION = "0.1"
OperationKind.SET_PROPERTY
```

Supported executable Decision keys:

```text
P1 / run / bold
P2 / run / font_size
P3 / paragraph / spacing.line
P4 / paragraph / alignment
```

Known deterministic keys outside the planner slice produce `PlanningStatus.UNSUPPORTED`, never silent omission.

## PlanningResult

Statuses are frozen as:

```text
planned
skipped
unsupported
```

Only `deterministic_change` on a supported slot produces a PlannedOperation.

`no_action`, `human_choice`, `review`, and `preserve` yield `skipped` without an operation.

Invariant:

```text
status == planned  IFF  operation is not None
```

## Compare-and-set semantics

Every `SET_PROPERTY` operation is semantic compare-and-set intent:

```text
precondition_observed = decision.observed
desired_value = decision.desired_value
```

with only the permitted typed materialization for font size:

```text
Decimal("12") -> LengthValue(Decimal("12"), "pt")
```

Invariants:

```text
precondition_observed is not None
desired_value is not None
precondition_observed != desired_value
rule_ref != None for deterministic_change
```

The planner never converts semantic values to OOXML units such as half-points or twips.

## Frozen target/provenance model

Each PlannedOperation preserves:

- DecisionKey;
- target_type;
- structural_path;
- physical_hash;
- target_class;
- aspect_id;
- property_slot;
- precondition_observed;
- desired_value;
- decision_ref.

`decision_ref` is frozen as:

```text
sha256(serialize_decision(decision))
```

`physical_hash` must be 64 lowercase hexadecimal characters, matching parser output.

`target_class` must be a non-empty string.

## Source document envelope

OperationPlan carries:

```text
SourceDocumentRef:
    package_sha256
    parser_version
```

and in v0.1:

```text
planned_story_part = "word/document.xml"
```

The source document fingerprint is the existing PhysicalIR package sha256; no new package hash is computed by the planner.

The three stale/drift anchors frozen for future SafetyGate are:

1. package sha256;
2. target physical_hash;
3. semantic precondition_observed.

## Upstream versions

The envelope records:

- analysis_formatting_version;
- classification_version;
- decision_version;
- decision_vocabulary_version.

Decision version and Decision Vocabulary version are bound against the Decisions themselves.

Analysis formatting version and classification version are currently orchestrator assertions because the frozen Decision model does not serialize them. This is an explicit non-blocking debt; future SafetyGate must not treat those two values as cryptographically bound provenance without an additional pipeline-context mechanism.

## source_decisions_hash

The plan carries an order-independent `source_decisions_hash`, derived from a canonically framed JSON array of canonically serialized Decisions after deterministic sorting.

Same logical Decision set in any caller order must yield identical hash and identical full OperationPlan bytes.

## Aggregation rules

Duplicate and conflict handling is strict:

- identical duplicate Decisions -> aggregation error;
- same physical target + same DecisionKey + same before/after -> duplicate operation error;
- same physical target + same DecisionKey + different precondition or desired -> conflict error;
- no silent deduplication;
- no winner chosen by order.

`target_class` is intentionally NOT part of physical operation identity. Divergent target_class values for the same physical target+slot are an upstream contradiction, not two distinct mutation targets.

## Deterministic ordering

`operations` and `planning_results` are canonically ordered for deterministic serialization.

This ordering is explicitly NOT document/application order; lexicographic structural_path ordering is acceptable for v0.1 because only independent SET_PROPERTY operations exist.

## Empty and partial plans

An empty OperationPlan is valid.

A mixed set of Decisions may yield planned, skipped and unsupported PlanningResults simultaneously. Supported deterministic operations remain in the executable operation tuple; unsupported slice items remain visible in the planning trail.

Conflict/duplicate/integrity errors fail aggregation instead of producing a partial ambiguous plan.

## Adversarial audit findings fixed before freeze

The final audit found and fixed:

1. BLOCKER — whole-plan bytes were caller-order dependent because `planning_results` preserved input order;
2. BLOCKER — `target_class` participated in conflict identity, allowing two operations on the same physical slot when classification labels diverged;
3. IMPORTANT — OperationTarget physical_hash accepted arbitrary non-empty strings instead of parser-compatible sha256 hex;
4. IMPORTANT — empty target_class was accepted;
5. MINOR — UpstreamVersions provenance semantics were ambiguous and were documented as bound values vs orchestrator assertions.

All fixes were applied in the same branch and validated before merge.

## Frozen E2E

```text
DOCX
-> Parser
-> Analysis
-> Classification
-> TargetClassification
-> Decision
-> OperationPlan
```

without manual target_class.

Audited outcome:

- bold true -> false => planned SET_PROPERTY with precondition true and desired false;
- font_size 11pt -> 12pt => planned SET_PROPERTY with typed pt values;
- spacing already compliant => skipped;
- alignment already compliant => skipped;
- exactly 2 executable operations;
- real PhysicalIR package_sha256 carried in the plan.

## Still out of scope

- SafetyGate;
- TransformLog;
- XML patch generation/application;
- half-point/twip conversion;
- structural operations;
- secondary-story execution;
- set-from-absent;
- operation/plan UUIDs;
- pipeline-context hash binding Analysis/Classification provenance.

## Reopening rule

This freeze reopens only for test failure, technical impossibility, contradiction with a frozen upstream contract, explicit scope change, or a newly identified safety risk.
