# Decisão 0030 — TransformLog / Execution Record v0.1 contract

Status: **PROPOSED — audited contract before implementation**

Date: 2026-09-08

## 1. Purpose

TransformLog v0.1 is the deterministic forensic record of a transformation that was **actually applied** by the frozen Patcher/Applicator v0.1.

It does not decide, authorize, validate, patch, re-open, or mutate DOCX content.

Principle:

**OperationPlan records intent; SafetyGate records clearance/blocking; PatchResult records execution outcome; TransformRecord records an applied transformation as immutable provenance.**

## 2. Sequencing clarification

Earlier conceptual architecture mentioned `SafetyGate -> TransformLog -> XML patch`. The executable architecture frozen in 0029 clarifies the truthful order.

A finalized TransformRecord requires both input and output package hashes, so it can only exist after a successful patch:

```text
GateClearedOperation
+ exact package snapshot
→ Patcher
→ PatchResult(APPLIED)
+ source Decision
→ TransformRecord
```

A pre-patch object would only repeat execution intent already represented by `PlannedOperation` / `GateClearedOperation`.

TransformRecord is not a new authorization layer and cannot make a rejected/blocked action executable.

## 3. Scope v0.1

TransformLog v0.1 records only successful transformations produced by Patcher v0.1:

```text
P1 / run / bold
P2 / run / font_size
```

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

Those belong to later processing/report orchestration.

## 4. Public construction boundary

Conceptual API:

```text
build_transform_record(
    cleared_operation: GateClearedOperation,
    patch_result: PatchResult,
    source_decision: Decision,
) -> TransformRecord
```

No DOCX/package bytes are accepted.

TransformLog MUST NOT parse or inspect OOXML and MUST NOT recompute semantic formatting.

`source_decision` is included only to make normative provenance durable and self-contained enough for future reporting. The builder does not re-evaluate the Decision.

## 5. Applied-only invariant

A TransformRecord may be created only when:

```text
patch_result.status == applied
```

Rejected PatchResult => `TransformLogContractError`; no record.

Blocked SafetyGate results never reach the builder because they cannot emit `GateClearedOperation`.

Execution exceptions do not produce TransformRecord v0.1.

**Absence of a TransformRecord is not evidence of success or failure by itself.**

A complete Processing Report must later combine SafetyGateReport + PatchResult + TransformRecord(s), and optionally non-applied Decision outcomes.

## 6. Cross-binding before record creation

The builder MUST fail fast unless all bindings hold.

### PatchResult ↔ GateClearedOperation

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

PatchResult's frozen invariant already guarantees:

```text
patch_result.output_package_sha256
==
sha256(patch_result.output_package_bytes)
```

The builder does not receive bytes and does not repeat that calculation.

### Decision ↔ PlannedOperation

Require:

```text
sha256(serialize_decision(source_decision))
==
cleared_operation.operation.decision_ref
```

and require the already-frozen semantic correspondences:
- Decision target addresses the same target_type / structural_path / physical_hash / target_class / aspect_id / property_slot as the operation target;
- Decision actionability is `deterministic_change`;
- Decision observed value equals `operation.precondition_observed`;
- Decision desired_value equals `operation.desired_value`;
- Decision rule_ref is present for an executable deterministic change under the frozen Decision/SafetyGate contract.

Any impossible mismatch is `TransformLogIntegrityError`, never a normal record state.

## 7. TransformRecord v0.1

Proposed frozen model:

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

Where:
- `profile_ref` is copied from the bound source Decision;
- `rule_ref` is copied from the bound source Decision;
- `target` is copied/reused from the embedded PlannedOperation.

`target` carries:
- target_type;
- structural_path;
- physical_hash (BEFORE mutation);
- target_class;
- aspect_id;
- property_slot.

The record does not store a post-transform physical_hash.

## 8. Why normative provenance is copied

`decision_ref` remains the cryptographic lineage anchor, but by itself it requires the original Decision object to be retained elsewhere before a later report can answer:

- which profile version governed the correction?;
- which rule caused the correction?;
- which rule path/aspect was applied?

`ProfileRef` and `RuleRef` are already small frozen domain objects. Copying them avoids a fragile future dependency on a separate Decision archive and allows the reporting layer to explain the correction without re-reading the DOCX or recovering historical Decision objects.

The full Decision is NOT embedded.

## 9. Why GateClearedOperation / PatchResult are not embedded

TransformRecord must not embed either artifact wholesale.

Reasons:
- GateClearedOperation contains execution-bound token semantics no longer needed after execution;
- PatchResult contains full output DOCX bytes;
- TransformRecord should remain small and safe for persistence/report inclusion.

Lineage remains bound by:
- `decision_ref`;
- `operation_ref`;
- `operation_plan_ref`;
- input/output package hashes;
- copied ProfileRef/RuleRef.

## 10. Values remain semantic

`precondition_observed` and `desired_value` are copied directly from PlannedOperation after Decision binding is proven.

Examples:

```text
bold:
true → false
```

```text
font_size:
LengthValue(11 pt) → LengthValue(12 pt)
```

TransformLog MUST NOT expose:
- `w:b`;
- `w:val="0"`;
- half-points;
- raw XML;
- ZipInfo.

OOXML translation remains exclusively a Patcher concern.

## 11. changed_part

For v0.1:

```text
changed_part == "word/document.xml"
```

Copied from PatchResult and checked against the frozen Patcher v0.1 scope.

TransformLog does not discover changed parts.

## 12. Target path before/after in v0.1

Patcher v0.1 performs only property-level mutation of an existing run and its postcondition resolves the same target structural_path on the output document.

Therefore, for v0.1:

**`target.structural_path` is the stable location identifier for both the pre-transform and post-transform snapshot.**

No redundant `output_structural_path` is stored.

This is valid only for the frozen bold/font_size property slice. Future structural MOVE/INSERT/MERGE operations MUST revisit this invariant under a new TransformLog version/decision.

This stable path is sufficient for a later review/highlight layer to locate the transformed run in the corresponding output snapshot, while package hashes ensure the path is interpreted against the correct snapshot.

## 13. No timestamps

TransformRecord has no:
- wall-clock timestamp;
- duration;
- hostname;
- random id;
- UUID.

Reason:
- deterministic serialization;
- timestamps are orchestration/observability metadata, not transformation semantics.

A future processing session may attach timing metadata outside TransformRecord.

## 14. Deterministic serialization

Canonical serialization follows the frozen Decision/OperationPlan pattern:
- dataclasses -> objects;
- enums -> string values;
- Decimal -> strings;
- tuples -> arrays;
- sorted keys;
- compact separators;
- UTF-8;
- no timestamp/random/locale.

APIs:

```text
serialize_transform_record(record) -> bytes
transform_ref(record) -> sha256 hex
```

```text
transform_ref
=
sha256(serialize_transform_record(record))
```

`transform_ref` is derived and not stored inside TransformRecord.

## 15. Determinism invariant

Given the same:

```text
GateClearedOperation
+ PatchResult(APPLIED)
+ source Decision
```

construction and serialization must produce byte-identical serialization and the same transform_ref.

Clock, environment, caller order and hash seed must not affect bytes.

## 16. One record per applied patch

Patcher v0.1 applies exactly one GateClearedOperation per call:

```text
1 APPLIED PatchResult
→ exactly 1 TransformRecord
```

There is no batch TransformLog envelope in v0.1.

A future processing/session layer may hold:

```text
tuple[TransformRecord, ...]
```

and define actual application order explicitly.

Do NOT infer application order by sorting transform_ref, structural_path, operation_ref, or any canonical serialization order.

## 17. Package lineage

For future sequential processing:

```text
record N.output_package_sha256
==
record N+1.input_package_sha256
```

v0.1 records the hashes but does not validate a multi-record chain because no batch/session envelope exists yet.

Chain validation belongs to future orchestration.

## 18. Target identity after mutation

No post-transform physical_hash is required in v0.1.

Rationale:
- Patcher already validates the produced document before APPLIED;
- output package SHA binds the complete output snapshot;
- the same structural_path is proven usable post-patch for this property-only slice;
- deriving a new physical hash would require TransformLog to reopen bytes, violating the no-DOCX boundary;
- the next operation is generated from a fresh Parser/Analysis cycle and carries a fresh physical_hash.

If diagnostics later require `target_physical_hash_after`, it should preferably be emitted by Patcher rather than recomputed by TransformLog, under new versioning.

## 19. Error model

```text
TransformLogError
TransformLogContractError
TransformLogIntegrityError
```

`TransformLogContractError`:
- wrong input types;
- PatchResult not APPLIED;
- malformed/unsupported artifact or version.

`TransformLogIntegrityError`:
- PatchResult ↔ GateClearedOperation ref/hash mismatch;
- Decision ref mismatch;
- Decision ↔ operation target/key/observed/desired mismatch;
- missing normative provenance that should exist under frozen upstream invariants;
- impossible embedded provenance inconsistency.

There is no `rejected` TransformRecord status in v0.1.

## 20. Version

```text
TRANSFORM_LOG_VERSION = "0.1"
```

Any semantic field change or canonical serialization change requires explicit versioning/decision.

## 21. Relationship to future user-facing outputs

TransformRecord is forensic provenance, not prose.

A later Processing Report can derive, without re-reading DOCX merely to discover what changed:

```text
Elemento: corpo do texto / heading etc.
Aspecto: negrito ou tamanho da fonte
Antes: valor semântico observado
Depois: valor semântico desejado/aplicado
Perfil: profile_id + profile_version
Regra: rule_id (+ path quando disponível)
Local: structural_path
Resultado: corrigido automaticamente
Snapshot antes/depois: package hashes
```

A later review/highlight DOCX can use the TransformRecord structural_path against the bound output snapshot to locate the changed run for this v0.1 property slice.

Human labels, prose, color/highlight style and warning wording remain outside TransformLog.

## 22. Required tests before freeze

At minimum:
1. build from valid GateClearedOperation + APPLIED PatchResult + bound source Decision;
2. rejected PatchResult cannot produce record;
3. raw PlannedOperation cannot substitute GateClearedOperation;
4. missing/wrong Decision type fails contract;
5. operation_ref mismatch fail-fast;
6. operation_plan_ref mismatch fail-fast;
7. input package SHA mismatch fail-fast;
8. decision_ref hash mismatch fail-fast;
9. Decision target mismatch fail-fast;
10. Decision observed mismatch fail-fast;
11. Decision desired mismatch fail-fast;
12. Decision not deterministic_change fails integrity;
13. missing rule_ref under executable deterministic change fails integrity;
14. decision_ref copied exactly;
15. profile_ref copied exactly;
16. rule_ref copied exactly;
17. target copied exactly including pre-transform physical_hash;
18. precondition_observed copied exactly;
19. desired_value copied exactly;
20. patcher_version copied exactly;
21. output package SHA copied exactly;
22. changed_part copied exactly;
23. no output package bytes stored;
24. no GateClearedOperation embedded;
25. no PatchResult embedded;
26. no full Decision embedded;
27. bool serialization deterministic;
28. LengthValue/Decimal serialization deterministic;
29. ProfileRef/RuleRef serialization deterministic;
30. serialization stable across PYTHONHASHSEED;
31. transform_ref equals sha256(serialized bytes);
32. same inputs produce same bytes/ref repeatedly;
33. no timestamps/random/UUID;
34. construction performs no file/network/XML/package IO;
35. JSON representation roundtrips without loss of fields needed for reporting;
36. v0.1 output structural_path equals recorded path under real Patcher E2E;
37. full frozen regression suite preserved.

## 23. Explicit non-goals / debts

- processing/session envelope;
- multi-record chain validator;
- user-facing Processing Report implementation;
- review/highlight DOCX implementation;
- rejected/blocked event ledger;
- exception telemetry;
- target post-physical-hash;
- wall-clock audit timestamps;
- signatures/cryptographic attestations;
- persistence/database schema;
- export format beyond deterministic canonical serialization.

## 24. Audit resolution

Contract audit conclusions before implementation:

1. **Applied-only semantics are correct**: a transformation log should never pretend that blocked/rejected attempts are transformations.
2. **Decision normative provenance was initially under-specified**: `decision_ref` alone would force later reports to retain/recover the original Decision. The contract now requires the bound source Decision as construction input and copies only ProfileRef + RuleRef.
3. **OperationTarget should be reused/copied as a frozen domain object**, not flattened into duplicate scalar fields.
4. **Lineage is sufficient after hardening**: decision_ref + operation_ref + operation_plan_ref + profile/rule refs + package hashes.
5. **Output DOCX bytes remain excluded**.
6. **No post-transform target hash is required for the v0.1 property-only slice**.
7. **No timestamps is correct** for deterministic domain provenance.
8. **No ordinary TransformRecord rejection/status is needed**.
9. **TransformLog remains completely free of DOCX/XML/package IO**.
10. **The frozen structural_path is sufficient for later review/highlight location in v0.1**, because the Patcher postcondition proves it still resolves after property-only mutation.

## 25. Implementation gate

This contract is now ready for implementation audit planning, but remains **PROPOSED** until implementation, tests and freeze decision complete.

Implementation MUST NOT expand scope beyond this contract without reopening 0030.
