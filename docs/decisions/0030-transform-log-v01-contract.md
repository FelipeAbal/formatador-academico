# Decisão 0030 — TransformLog / Execution Record v0.1 contract

Status: **PROPOSED — implemented on audit branch; pending suite/freeze**

Date: 2026-09-08

## 1. Purpose

TransformLog v0.1 is the deterministic forensic record of a transformation **actually applied** by Patcher/Applicator v0.1.

It does not decide, authorize, patch, reopen or mutate DOCX content.

Principle:

**OperationPlan records intent; SafetyGate records clearance/blocking; PatchResult records execution outcome; TransformRecord records immutable provenance of an applied transformation.**

## 2. Truthful sequence

A finalized record exists only after a successful patch:

```text
GateClearedOperation
+ exact package snapshot
→ Patcher
→ PatchResult(APPLIED)
+ bound source Decision
→ TransformRecord
```

A pre-patch TransformRecord would merely duplicate execution intent already represented by PlannedOperation/GateClearedOperation.

## 3. v0.1 slice

Only:

```text
P1 / run / bold
P2 / run / font_size
```

Exactly one applied patch produces exactly one TransformRecord.

Blocked SafetyGate results, rejected PatchResults, exceptions, human warnings, timestamps, multi-operation transactions and raw XML are outside TransformLog v0.1.

## 4. Public API

```text
build_transform_record(
    cleared_operation: GateClearedOperation,
    patch_result: PatchResult,
    source_decision: Decision,
) -> TransformRecord
```

No DOCX/package bytes are accepted.

No XML, ZIP, filesystem, network, clock, random or LLM access is permitted.

The source Decision is supplied only to make normative provenance durable. The builder does not re-evaluate compliance or rules.

## 5. Applied-only invariant

A record can be built only when:

```text
patch_result.status == applied
```

Rejected PatchResult → TransformLogContractError.

Absence of a TransformRecord alone does not mean success or failure; a later Processing Report combines SafetyGateReport + PatchResult + TransformRecord(s).

## 6. Cross-binding

### PatchResult ↔ GateClearedOperation

Require:

```text
patch_result.operation_ref == cleared_operation.operation_ref
patch_result.operation_plan_ref == cleared_operation.operation_plan_ref
patch_result.input_package_sha256 == cleared_operation.current_package_sha256
```

PatchResult already guarantees:

```text
output_package_sha256 == sha256(output_package_bytes)
```

TransformLog does not receive or rehash those bytes.

### GateClearedOperation ↔ embedded PlannedOperation

Require again:

```text
operation_ref == sha256(canonical PlannedOperation serialization)
```

and require the operation to remain inside the frozen TransformLog/Patcher v0.1 slice.

### source Decision ↔ PlannedOperation

Require:

```text
sha256(serialize_decision(source_decision))
== operation.decision_ref
```

Require exact target correspondence for:
- target_type;
- structural_path;
- physical_hash;
- target_class;
- aspect_id;
- property_slot.

Require:
- Decision.actionability == deterministic_change;
- rule_ref present;
- ProfileRef and RuleRef profile id/version agree;
- RuleRef.aspect_id agrees with target aspect.

### Value binding and frozen planner typing

The OperationPlan v0.1 intentionally changes semantic representation for font size:

```text
Decision font_size value: Decimal points
→ OperationPlan value: LengthValue(value, unit="pt")
```

Therefore TransformLog MUST validate **planner-equivalent semantics**, not raw object identity:

```text
bold:
Decision bool == PlannedOperation bool
```

```text
font_size:
LengthValue(Decision Decimal, "pt") == PlannedOperation LengthValue
```

The builder does not call the planner, re-plan, or choose values; it only validates this frozen projection.

Any impossible mismatch is TransformLogIntegrityError.

## 7. TransformRecord model

```text
TransformRecord:
    transform_log_version
    patcher_version
    operation_ref
    operation_plan_ref
    decision_ref
    profile_ref
    rule_ref
    target
    precondition_observed
    desired_value
    input_package_sha256
    output_package_sha256
    changed_part
```

`target` is the frozen OperationTarget and contains the **pre-transform** physical_hash.

The record deliberately excludes:
- output_package_bytes;
- GateClearedOperation object;
- PatchResult object;
- full Decision object;
- raw XML/OOXML values.

## 8. Why ProfileRef/RuleRef are copied

`decision_ref` alone would force future reporting to retain/recover the full historical Decision just to answer which profile/rule caused the correction.

ProfileRef and RuleRef are small frozen domain objects, so they are copied into TransformRecord after Decision binding is proven.

This makes the future report self-contained enough to explain:
- profile id/version;
- rule id/path/aspect;
- before/after semantic values;
- location and package lineage.

## 9. Semantic values

TransformRecord copies values from the **PlannedOperation**, after Decision binding is proven.

Examples:

```text
bold: true → false
font_size: LengthValue(11 pt) → LengthValue(12 pt)
```

OOXML forms such as `w:b`, `w:val="0"` and half-points remain exclusively Patcher concerns.

## 10. Location and package lineage

For v0.1:

```text
changed_part == "word/document.xml"
```

The Patcher property-only postcondition proves the same structural_path still resolves after the patch, so:

**target.structural_path is the stable pre/post location identifier for bold/font_size v0.1.**

No redundant output_structural_path is stored.

Package hashes provide snapshot lineage:

```text
input_package_sha256 → output_package_sha256
```

A future multi-record session may validate:

```text
record N.output_package_sha256 == record N+1.input_package_sha256
```

but no batch/session envelope exists in v0.1.

## 11. No post-transform physical_hash

Not required in v0.1 because:
- Patcher validates output before APPLIED;
- output package SHA binds the complete snapshot;
- the same structural_path is proven usable post-patch;
- the next pipeline pass generates a fresh target physical_hash.

If later needed, post-transform target hash should preferably be emitted by Patcher under new versioning, not recomputed by TransformLog.

## 12. Deterministic serialization

```text
TRANSFORM_LOG_VERSION = "0.1"
```

Canonical serialization follows the frozen Decision/OperationPlan pattern:
- dataclasses → objects;
- enums → string values;
- Decimal → strings;
- sorted keys;
- compact separators;
- UTF-8;
- no time/random/locale/environment.

APIs:

```text
serialize_transform_record(record) -> bytes
transform_ref(record) -> sha256 hex
```

```text
transform_ref = sha256(serialize_transform_record(record))
```

transform_ref is derived and not stored in the record.

## 13. Error model

```text
TransformLogError
TransformLogContractError
TransformLogIntegrityError
```

Contract error:
- wrong input type;
- PatchResult not APPLIED;
- unsupported artifact/version/slice.

Integrity error:
- ref/hash binding mismatch;
- Decision hash mismatch;
- target/value/provenance mismatch;
- impossible upstream inconsistency.

There is no TransformRecord status/rejected state.

## 14. Future reporting/review sufficiency

Without rereading DOCX merely to rediscover what changed, a future Processing Report can derive:

```text
Elemento/target_class
Aspecto/property_slot
Antes/precondition_observed
Depois/desired_value
Perfil/profile_ref
Regra/rule_ref
Local/structural_path
Resultado/corrigido automaticamente
Snapshot antes/depois/package hashes
```

A future review/highlight DOCX may use the recorded structural_path against the bound output snapshot for this property-only slice.

Human prose, labels, warning wording and visual highlighting remain outside TransformLog.

## 15. Required validation before freeze

At minimum cover:
- valid applied construction;
- rejected patch refusal;
- raw PlannedOperation refusal;
- ref/plan/input SHA mismatches;
- source Decision hash binding;
- target mismatch;
- observed/desired mismatch;
- deterministic_change requirement;
- rule/profile provenance binding;
- unsupported slice refusal;
- copied refs/target/semantic values/package hashes;
- no output bytes/full upstream artifacts embedded;
- bool and font_size Decimal→LengthValue serialization;
- deterministic repeated serialization/ref;
- PYTHONHASHSEED stability;
- no time/random/IO/XML/network behavior;
- real E2E Parser→Analysis→Classification→Decision→OperationPlan→SafetyGate→Patcher→TransformRecord;
- stable output structural_path in that E2E;
- full frozen regression suite.

## 16. Non-goals/debts

- processing/session envelope;
- multi-record chain validator;
- rejected/blocked event ledger;
- user-facing Processing Report implementation;
- review/highlight DOCX implementation;
- persistence/database schema;
- signatures/attestations;
- target post-physical-hash;
- timestamps/telemetry;
- structural operations.

## 17. Freeze gate

This contract remains **PROPOSED** until implementation audit and full suite are green.

Any semantic expansion beyond this document requires reopening 0030 or a new versioned decision.
