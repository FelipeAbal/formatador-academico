# Decisão 0030 — TransformLog / Execution Record v0.1 contract

Status: **PROPOSED — contract before implementation**

Date: 2026-09-08

## 1. Purpose

TransformLog v0.1 is the deterministic forensic record of a transformation that was **actually applied** by the frozen Patcher/Applicator v0.1.

It does not decide, authorize, validate, patch, re-open, or mutate DOCX content.

Principle:

**OperationPlan records intent; SafetyGate records clearance/blocking; PatchResult records execution outcome; TransformRecord records an applied transformation as immutable provenance.**

## 2. Sequencing clarification

The earlier conceptual architecture mentioned `SafetyGate -> TransformLog -> XML patch`. That ordering is now clarified by the executable pipeline frozen in 0029.

A truthful TransformRecord can only be finalized after a patch has succeeded, because it must bind both the input and output package hashes.

Frozen conceptual sequence for v0.1:

```text
GateClearedOperation
+ exact package snapshot
→ Patcher
→ PatchResult(APPLIED)
→ TransformRecord
```

This is not a new authorization layer and does not weaken any SafetyGate/Patcher invariant.

A pre-patch object would be execution intent, already represented by `PlannedOperation`/`GateClearedOperation`, and therefore is not created.

## 3. Scope v0.1

TransformLog v0.1 records only successful transformations produced by Patcher v0.1:

```text
P1 / run / bold
P2 / run / font_size
```

It must be generic enough to carry the frozen `PlannedOperation` semantics without hard-coding OOXML values.

Outside v0.1:
- blocked SafetyGate results;
- rejected PatchResult outcomes;
- exceptions/internal failures;
- human warnings/review messages;
- report prose;
- timestamps/durations;
- usernames/machine identity;
- UI events;
- multi-operation transaction logs;
- secondary stories;
- raw XML snapshots/diffs.

Those belong to later processing/report orchestration, not TransformLog.

## 4. Public construction boundary

Conceptual API:

```text
build_transform_record(
    cleared_operation: GateClearedOperation,
    patch_result: PatchResult,
) -> TransformRecord
```

No DOCX/package bytes are accepted.

TransformLog MUST NOT parse or inspect OOXML and MUST NOT recompute semantic formatting.

The builder trusts only invariants already proven by the frozen artifacts and verifies their cross-binding.

## 5. Applied-only invariant

A TransformRecord may be created only when:

```text
patch_result.status == applied
```

Rejected PatchResult => contract error; no TransformRecord.

Blocked SafetyGate results never reach this builder because they cannot emit `GateClearedOperation`.

Unexpected execution exceptions also do not produce TransformRecord v0.1.

This means:

**absence of a TransformRecord is not evidence of success or failure by itself.**

For a complete processing report, later orchestration must combine SafetyGateReport + PatchResult + TransformRecord(s).

## 6. Cross-binding before record creation

The builder MUST fail fast unless all bindings hold:

```text
patch_result.operation_ref
==
cleared_operation.operation_ref
```

```text
patch_result.operation_plan_ref
==
cleared_operation.operation_plan_ref
```

```text
patch_result.input_package_sha256
==
cleared_operation.current_package_sha256
```

and PatchResult's frozen invariant already guarantees:

```text
patch_result.output_package_sha256
==
sha256(patch_result.output_package_bytes)
```

The builder does not receive the bytes and therefore does not repeat that hash calculation.

Any mismatch is `TransformLogIntegrityError`, never an ordinary record state.

## 7. TransformRecord v0.1

Proposed frozen model:

```text
TransformRecord:
    transform_log_version
    patcher_version
    operation_ref
    operation_plan_ref
    decision_ref
    target
    precondition_observed
    desired_value
    input_package_sha256
    output_package_sha256
    changed_part
```

Where `target` is the frozen `OperationTarget` copied/reused from the embedded `PlannedOperation` and therefore carries:
- target_type;
- structural_path;
- physical_hash (BEFORE mutation);
- target_class;
- aspect_id;
- property_slot.

`physical_hash` in v0.1 is explicitly the **pre-transform** physical hash inherited from the operation. No post-transform target hash is invented or recomputed.

## 8. Why the operation is not embedded wholesale

TransformRecord should not simply embed the entire `GateClearedOperation` or `PatchResult` objects.

Reasons:
- `GateClearedOperation` contains execution-bound token semantics that are no longer needed after execution;
- `PatchResult` contains the full output DOCX bytes, which MUST NOT be duplicated into the forensic log;
- the record should remain small, serializable, and safe to include in future reports.

Instead, TransformRecord copies the minimal semantic/provenance fields needed to explain and bind the applied change.

The authoritative lineage remains recoverable through `operation_ref`, `operation_plan_ref`, and `decision_ref`.

## 9. Values remain semantic

`precondition_observed` and `desired_value` are copied directly from the frozen `PlannedOperation`.

Examples:

```text
bold:
true → false
```

```text
font_size:
LengthValue(11 pt) → LengthValue(12 pt)
```

TransformLog MUST NOT expose OOXML representations such as:
- `w:b`;
- `w:val="0"`;
- half-points;
- raw XML;
- ZipInfo.

That translation belongs exclusively to the Patcher.

## 10. changed_part

For v0.1:

```text
changed_part == "word/document.xml"
```

The value is copied from PatchResult and must also be compatible with the frozen Patcher v0.1 scope.

TransformLog does not infer or discover changed parts.

## 11. No timestamps

TransformRecord has no:
- wall-clock timestamp;
- duration;
- hostname;
- random id;
- UUID.

Reason:
- deterministic serialization;
- no false precision about execution environment;
- timestamps are orchestration/observability metadata, not transformation semantics.

A future external processing session may attach timing metadata outside TransformRecord.

## 12. Deterministic serialization

Canonical serialization follows the frozen Decision/OperationPlan pattern:
- dataclasses -> objects;
- enums -> string values;
- Decimal -> strings;
- tuples -> arrays;
- sorted keys;
- compact separators;
- UTF-8;
- no timestamp/random/locale.

Proposed APIs:

```text
serialize_transform_record(record) -> bytes
transform_ref(record) -> sha256 hex
```

with:

```text
transform_ref
=
sha256(serialize_transform_record(record))
```

`transform_ref` is DERIVED and is not stored inside TransformRecord, avoiding self-referential serialization.

## 13. Determinism invariant

Given the same:

```text
GateClearedOperation
+
PatchResult(APPLIED)
```

construction and serialization must produce byte-identical TransformRecord serialization and the same `transform_ref`.

Caller order, clock, environment and hash seed must not affect bytes.

## 14. One record per applied patch

Because Patcher v0.1 applies exactly one GateClearedOperation per call:

```text
1 applied PatchResult
→ exactly 1 TransformRecord
```

There is no batch `TransformLog` envelope in v0.1.

A future processing/session layer may hold:

```text
tuple[TransformRecord, ...]
```

and define chronological/document application order explicitly.

Do NOT infer application order by sorting `transform_ref`, structural_path, or any existing canonical order.

## 15. Package lineage

For sequential future processing, hashes naturally form a chain:

```text
record N.output_package_sha256
==
record N+1.input_package_sha256
```

TransformLog v0.1 records these hashes but does not itself validate a multi-record chain because it has no batch/session envelope.

Chain validation belongs to future orchestration.

## 16. Target identity after mutation

No post-transform `physical_hash` is required in v0.1.

Rationale:
- the Patcher already validates the produced document semantically before APPLIED;
- package output SHA binds the complete output snapshot;
- deriving a new target hash would require TransformLog to reopen/parse bytes, violating its no-DOCX boundary;
- the next operation will be generated from a fresh Parser/Analysis cycle and will carry its own fresh physical_hash.

If future diagnostics demonstrably require `target_physical_hash_after`, it must be added by a new version/decision, preferably emitted by the Patcher rather than recomputed by TransformLog.

## 17. Error model

Proposed:

```text
TransformLogError
TransformLogContractError
TransformLogIntegrityError
```

`TransformLogContractError`:
- wrong input types;
- PatchResult not APPLIED;
- malformed unsupported artifact/version.

`TransformLogIntegrityError`:
- operation_ref mismatch;
- operation_plan_ref mismatch;
- input package SHA mismatch;
- embedded operation/key/target provenance inconsistency that should be impossible under frozen upstream invariants.

There is no `rejected` TransformRecord status in v0.1.

## 18. Version

Proposed:

```text
TRANSFORM_LOG_VERSION = "0.1"
```

Any semantic field change or serialization change requires explicit versioning/decision.

## 19. Relationship to future user-facing report

TransformRecord is forensic provenance, not prose.

A later Processing Report may translate a record into user-facing content such as:

```text
Corpo do texto — negrito
Antes: ativado
Depois: desativado
Local: parágrafo/run identificado
Resultado: corrigido automaticamente
```

But TransformLog itself must not generate those labels or explanations.

It preserves enough stable information for a later reporting layer to do so without re-reading the DOCX merely to discover what was changed.

## 20. Required tests before freeze

At minimum:
1. build from valid GateClearedOperation + APPLIED PatchResult;
2. rejected PatchResult cannot produce record;
3. raw PlannedOperation cannot substitute GateClearedOperation;
4. operation_ref mismatch fail-fast;
5. operation_plan_ref mismatch fail-fast;
6. input package SHA mismatch fail-fast;
7. decision_ref copied exactly from operation;
8. target copied exactly, including pre-transform physical_hash;
9. precondition_observed copied exactly;
10. desired_value copied exactly;
11. patcher_version copied exactly;
12. output package SHA copied exactly;
13. changed_part copied exactly;
14. no output package bytes stored in record;
15. no GateClearedOperation object embedded;
16. no PatchResult object embedded;
17. bool serialization deterministic;
18. LengthValue/Decimal serialization deterministic;
19. serialization stable across PYTHONHASHSEED;
20. transform_ref equals sha256(serialized bytes);
21. same inputs produce same bytes/ref repeatedly;
22. no timestamps/random/UUID;
23. record construction performs no file/network/XML/package IO;
24. record can be JSON-roundtripped at serialization representation level without information loss needed for reporting;
25. full frozen regression suite preserved.

## 21. Explicit non-goals / debts

- processing/session envelope;
- multi-record chain validator;
- user-facing Processing Report;
- review/highlight DOCX;
- rejected/blocked event ledger;
- exception telemetry;
- target post-physical-hash;
- wall-clock audit timestamps;
- signatures/cryptographic attestations;
- persistence/database schema;
- export format beyond deterministic canonical serialization.

## 22. Audit questions before freeze

Before implementation/freeze, audit specifically:
1. whether applied-only semantics are sufficient for forensic provenance;
2. whether any field needed by future clean/review/report output is missing;
3. whether copying `OperationTarget` is preferable to duplicating scalar target fields;
4. whether `decision_ref + operation_ref + operation_plan_ref` is sufficient lineage;
5. whether output bytes must remain excluded;
6. whether no post-transform target hash creates a real forensic blind spot;
7. whether TransformLog should know active profile/rule provenance or leave that recoverable through `decision_ref`;
8. whether no timestamps is correct for domain-level deterministic provenance;
9. whether any ordinary rejection/status is actually needed;
10. whether TransformLog can remain completely free of DOCX/XML/package IO.
