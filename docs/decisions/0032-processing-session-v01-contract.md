# Decisão 0032 — Processing Session / Orchestration v0.1 contract

Status: **PROPOSED — audited implementation under CI validation**

Date: 2026-09-08

## 1. Purpose

Processing Session v0.1 is the deterministic orchestration layer that repeatedly invokes the frozen pipeline until automatic execution reaches a safe quiescent state for the current v0.1 slice.

It does not replace or weaken Parser, Analysis, Classification, Decision, OperationPlan, SafetyGate, Patcher, or TransformLog.

Principle:

**The session coordinates frozen components; it does not acquire new authority.**

`quiescent` is a technical automation state, not a claim that the document is fully conformant or needs no human review.

## 2. Pipeline per iteration

Every mutable iteration is rebuilt from the exact current package snapshot:

```text
current DOCX bytes
→ Parser
→ StyleCatalog / Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
→ at most ONE GateClearedOperation
→ Patcher
→ PatchResult
→ TransformRecord (APPLIED only)
→ next current DOCX bytes
```

After APPLIED, every remaining token from the old SafetyGateReport is discarded and the full pipeline is rerun. This preserves the single-operation semantics frozen in 0029.

## 3. Executable scope

Automatic execution is limited to:

```text
P1 / run / bold
P2 / run / font_size
```

Supported classification targets for rule binding:

```text
body
heading
```

Heading-level-specific rules are outside v0.1 because heading level is not preserved in frozen `TargetClassification`.

Outside v0.1:
- P3 spacing patching;
- P4 alignment patching;
- italic patching;
- long_quote/reference execution;
- tables/containers/numbering execution;
- secondary-story execution;
- structural MOVE/INSERT/MERGE;
- styles.xml mutation;
- review/highlight DOCX;
- final human-readable report.

## 4. Minimal orchestration profile

The frozen layers provide `ProfileRef` and `FormattingRule`, but no profile aggregate suitable for orchestration. v0.1 introduces only the minimum connector model; it is not the future UI/profile schema.

```text
RuleBinding:
    target_class
    target_type
    rule: FormattingRule

ProcessingProfile:
    profile_ref: ProfileRef
    bindings: tuple[RuleBinding, ...]
```

Requirements:

```text
target_class ∈ {body, heading}
target_type == run
(rule.aspect_id, rule.property_slot) ∈ {
    (P1, bold),
    (P2, font_size),
}
```

At most one binding per:

```text
(target_class, target_type, aspect_id, property_slot)
```

Duplicate/conflicting bindings are contract errors; caller order never resolves conflicts.

### Eager rule validation

Profile defects must fail even if the input document happens not to contain a matching target.

For the v0.1 executable slice:
- bold rule values are exact `bool`;
- font_size rule values are `Decimal` points;
- EXACT/SET values are checked eagerly;
- CONTAINMENT remains valid and is interpreted only by the frozen Decision Layer;
- rule_id, profile_id and profile_version are non-empty.

The session never chooses a desired value itself.

## 5. Target enumeration and application order

The session follows frozen classification document order.

For each eligible classified paragraph, real `run_raw` descendants are enumerated recursively in PhysicalIR child order, including supported run containers such as hyperlinks.

Run classification is produced only via:

```text
project_run_classification(run, paragraph_result)
```

Only classification results eligible for automatic use may enter Decision. The session never infers a target class.

Within the same run, matching bindings are canonically ordered by:

```text
(target_class, target_type, aspect_id, property_slot, rule_id, path_or_empty)
```

Therefore application order is:

```text
physical paragraph/run order
→ canonical binding order
```

OperationPlan canonical serialization order is explicitly NOT application order.

## 6. Decision generation

For every eligible run + matching binding:

```text
DecisionContext(
    DecisionKey(run, aspect_id, property_slot),
    projected TargetClassification,
    ProcessingProfile.profile_ref,
)
```

Observed formatting comes only from frozen Analysis plus `extract_resolved_value`; normative evaluation comes only from frozen `evaluate_target`.

The session MUST NOT:
- inspect raw OOXML for compliance;
- invent desired values;
- reinterpret RuleMode;
- downgrade Analysis ambiguity;
- promote abstention into body/heading.

## 7. Snapshot binding

Each iteration internally binds:

```text
package_sha256
PhysicalIR
StyleCatalog
ClassificationResults
Decisions
OperationPlan
SafetyGateReport
```

to exactly one current snapshot.

Mixing artifacts from different snapshots is `ProcessingSessionIntegrityError`.

The session additionally verifies that the set of GateResults corresponds exactly to the OperationPlan operations and that every cleared token maps back to its canonical Decision/operation.

## 8. One patch per iteration

From a compatible evaluation, select the earliest Decision-order CLEARED token that has not already been Patcher-rejected on this exact snapshot.

Call Patcher exactly once before any new mutation.

On APPLIED:
1. build exactly one TransformRecord from the bound source Decision;
2. verify input/output hash lineage;
3. append it in actual execution order;
4. replace the current snapshot with output bytes;
5. discard all old tokens and snapshot-local rejection suppression;
6. rebuild the complete pipeline.

Input bytes are never mutated in-place.

## 9. Patcher rejection semantics

A legitimate physical Patcher rejection does not stop independent later operations.

Suppression is scoped to:

```text
(current_package_sha256, operation_ref)
```

The exact same operation is not retried against the unchanged snapshot. After any successful independent patch changes the package SHA, suppression is reset and the fresh pipeline may legitimately produce/retry a semantically fresh operation.

Only these Patcher reasons may become ordinary `patch_rejected` findings in v0.1:
- `noncanonical_run_properties`;
- `duplicate_target_property`;
- `unrepresentable_value`.

Inside a correctly bound session these reasons are impossible and therefore fail fast as integrity errors, never findings:
- `snapshot_hash_mismatch`;
- `unsupported_operation`.

## 10. SafetyGate blocking

Blocked operations are never sent to Patcher.

A local block does not prevent independent cleared operations in a compatible context.

Global blocked context yields no executable token.

Only unresolved findings belonging to the final/current snapshot are returned. Stale blocked findings from an earlier snapshot are discarded after a successful patch; applied history is represented by TransformRecords.

## 11. Terminal statuses

```text
quiescent
quiescent_with_unapplied
operation_limit_reached
```

### quiescent

No final `deterministic_change` Decision remains in the bound v0.1 slice and there are no unresolved execution findings.

This does NOT mean there are no final `review`, `human_choice`, `preserve`, abstained classifications or unsupported content.

### quiescent_with_unapplied

At least one final `deterministic_change` remains because it is Gate-blocked or legitimately Patcher-rejected, while no further safely applicable operation remains.

### operation_limit_reached

The next safely applicable operation exists, but executing it would exceed the explicit applied-operation budget. No extra patch is applied.

This status is not success/quiescence.

## 12. Operation budget

Public API:

```text
max_applied_operations: int = 10000
```

Requirements:
- exact int; bool rejected;
- > 0;
- counts APPLIED patches/TransformRecords only;
- deterministic;
- no silent truncation.

The high default is a safety fuse, not a performance guarantee.

## 13. Cycle detection

Track all package SHA256 values seen after APPLIED patches, starting with input SHA.

If an APPLIED result produces any previously seen package SHA:

```text
ProcessingSessionIntegrityError
```

A cycle is an upstream/orchestration/executor contradiction and is never normalized into a result status.

## 14. Final machine-readable state

Before any non-exception terminal result, re-evaluate the final/current snapshot and return:

```text
final_classifications: tuple[ClassificationResult, ...]
final_decisions: tuple[Decision, ...]
```

Classifications are retained so abstention/non-applicability does not disappear silently under the product principle **“Na dúvida, marcar.”**

Decisions retain no_action/review/preserve/human_choice outcomes needed by later reporting.

## 15. SessionFinding

```text
SessionFinding:
    kind
    decision_ref
    operation_ref
    target
    reason
```

Kinds:
- `gate_blocked` → reason must be a frozen GateReason value;
- `patch_rejected` → reason must be one of the three allowed physical Patcher rejection reasons above;
- `operation_limit` → reason exactly `operation_limit_reached`.

Every finding must bind to a final deterministic-change Decision and its exact target.

Findings never embed DOCX bytes, GateClearedOperation, SafetyGateReport, or PatchResult.

## 16. ProcessingSessionResult

```text
ProcessingSessionResult:
    processing_session_version
    status
    profile_ref
    input_package_sha256
    output_package_sha256
    output_package_bytes
    transforms: tuple[TransformRecord, ...]
    final_classifications: tuple[ClassificationResult, ...]
    final_decisions: tuple[Decision, ...]
    findings: tuple[SessionFinding, ...]
```

No timestamp, UUID, hostname, network metadata or random id.

Required invariants:

```text
output_package_sha256 == sha256(output_package_bytes)
```

If transforms is empty:

```text
input_package_sha256 == output_package_sha256
```

Otherwise:

```text
first transform input == session input
last transform output == session output
each adjacent transform output == next transform input
```

`transforms` order is actual application order and is never re-sorted canonically.

All TransformRecords and final Decisions use the session ProfileRef.

Status/Decision/finding coherence is enforced by the public frozen result model.

## 17. Public API

```text
process_document(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = 10000,
) -> ProcessingSessionResult
```

Bytes in / bytes out. No filesystem path, network, wall clock, randomness, LLM or global mutable state.

## 18. Error model

```text
ProcessingSessionError
ProcessingSessionContractError
ProcessingSessionIntegrityError
```

Contract errors include malformed inputs/profile, unsupported bindings, invalid operation budget and a package that cannot produce the fully supported PhysicalIR/StyleCatalog state required by the frozen downstream pipeline.

Integrity errors include cross-snapshot artifact mixing, token/Decision/operation mismatch, impossible Patcher rejection, TransformRecord lineage mismatch, cycle detection and impossible GateResult mapping.

Frozen downstream exceptions are never silently downgraded into findings.

## 19. Determinism

Identical:

```text
package bytes
+ ProcessingProfile
+ max_applied_operations
```

must produce identical output bytes and result semantics in the supported runtime.

Caller binding order must not affect output bytes, TransformRecord order, final Decision order or finding order.

## 20. Current strictness on partial parser state

The frozen Classification Layer currently requires a fully `status == ok` PhysicalIR. Therefore Processing Session v0.1 also requires parser status `ok`.

A document with an otherwise usable body but malformed secondary story may produce parser status `partial` and is not processed automatically in v0.1. This is an inherited upstream limitation, not silently bypassed by orchestration.

Revisiting partial-story isolation requires an explicit upstream contract change; Session v0.1 does not weaken Classification to work around it.

## 21. No final report/review rendering yet

Processing Session returns orchestration state, not user-facing prose.

It does not generate:
- highlighted/review DOCX;
- final report prose;
- UI labels;
- “corrigido automaticamente” text.

Later layers will consume ordered TransformRecords, final classifications, final Decisions, findings and output bytes.

## 22. Required coverage before freeze

Coverage must include at least:
- no-change byte-identical quiescence;
- bold and font single changes;
- bold+font same run across fresh full reruns;
- multiple runs/paragraphs in physical order;
- caller binding order independence;
- hyperlink run traversal;
- heading-only binding;
- final classifications from final snapshot;
- classification abstention retention;
- final no_action Decisions;
- global/local Gate blocking behavior;
- legitimate Patcher rejection suppression and independent progress;
- retry only after snapshot change;
- impossible Patcher rejection fail-fast;
- TransformRecord chain integrity;
- operation limit;
- cycle fail-fast;
- input immutability;
- repeated/hashseed determinism;
- no runtime filesystem/network/clock/random/LLM use;
- profile type/conflict validation;
- SessionFinding reason vocabulary;
- status/finding/final-Decision public-model consistency;
- full frozen regression suite.

## 23. Audit resolution

The implementation audit resolved the pre-implementation questions as follows:

1. `ProcessingProfile + RuleBinding` is deliberately minimal and is **not** the final product profile schema.
2. Final classifications + final Decisions + findings + ordered TransformRecords preserve enough machine-readable state for later reporting/review without re-discovering applied history.
3. One-patch-per-full-rerun is intentionally conservative. Performance cost is accepted in v0.1 because it preserves SafetyGate/Patcher snapshot guarantees exactly.
4. Rejection suppression is safe because it is exact-snapshot scoped and resets after APPLIED.
5. Application order is physical document/run order plus canonical binding order and is proven independent of caller tuple order.
6. Returning only final unresolved findings is correct; stale intermediate conditions should not be presented as final failures after later successful mutation.
7. Operation budget is a visible safety fuse, never silent truncation.
8. Package-hash cycles are integrity failures, not business statuses.
9. Raw SafetyGateReport/PatchResult objects are not exposed in the terminal public result.
10. Classification abstentions are retained explicitly for later “na dúvida, marcar” reporting.
11. Status vocabulary uses `quiescent`, not `complete`, to avoid claiming full conformity.
12. GitHub Actions CI was added so regression execution no longer depends on paid external model credits.

## 24. Explicit debts / non-goals

- final user profile schema/validator/UI;
- heading-level-specific rules;
- paragraph P3/P4 execution;
- atomic multi-operation transaction/rollback;
- persistence/resume after interruption;
- human-readable Processing Report;
- review/highlight DOCX;
- timestamps/telemetry;
- secondary-story execution;
- partial-story automatic isolation;
- complex-script `w:szCs` correction;
- performance optimization for documents requiring very large numbers of sequential patches.

## 25. Implementation gate

Implementation exists on an isolated PR and may be frozen only after the final hardened head passes CI and independent static/adversarial inspection.
