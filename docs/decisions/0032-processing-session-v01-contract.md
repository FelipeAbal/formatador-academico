# Decisão 0032 — Processing Session / Orchestration v0.1 contract

Status: **PROPOSED — contract before implementation**

Date: 2026-09-08

## 1. Purpose

Processing Session v0.1 is the deterministic orchestration layer that repeatedly invokes the already-frozen pipeline until the current document reaches a quiescent state for the v0.1 executable slice.

It does not replace or weaken Parser, Analysis, Classification, Decision, OperationPlan, SafetyGate, Patcher, or TransformLog.

Principle:

**The session coordinates frozen components; it does not acquire new authority.**

## 2. Frozen pipeline reused per iteration

For every mutable iteration the session MUST rebuild state from the current package snapshot:

```text
current DOCX bytes
→ Parser
→ StyleCatalog / Analysis
→ Classification
→ Decision
→ OperationPlan
→ SafetyGate
→ at most ONE selected GateClearedOperation
→ Patcher
→ PatchResult
→ TransformRecord (if APPLIED)
→ next current DOCX bytes
```

After an APPLIED patch, no remaining token from the old SafetyGateReport may be executed. The complete pipeline/gate is rerun on the new snapshot, preserving the single-operation semantics frozen in 0029.

## 3. Scope v0.1

Automatic session execution is limited to the Patcher/TransformLog slice:

```text
P1 / run / bold
P2 / run / font_size
```

Target classes supported by rule binding:

```text
body
heading
```

`heading` is one class in the frozen Decision projection; heading-level-specific rules are outside v0.1 because Classification metadata level is not carried by `TargetClassification`.

Outside v0.1:
- P3 spacing patching;
- P4 alignment patching;
- italic patching;
- long_quote/reference execution;
- tables/containers/numbering execution;
- secondary-story execution;
- structural MOVE/INSERT/MERGE;
- `styles.xml` mutation;
- review/highlight DOCX generation;
- final human-readable report generation.

## 4. Minimal processing profile aggregate

The repository currently has `ProfileRef` and `FormattingRule`, but no aggregate `ValidatedProfile` object suitable for orchestration.

v0.1 introduces only the minimum binding needed to connect a rule to a classified target, without claiming to be the final UI/profile schema.

```text
RuleBinding:
    target_class
    target_type
    rule: FormattingRule
```

v0.1 requires:

```text
target_class ∈ {body, heading}
target_type == run
(rule.aspect_id, rule.property_slot) ∈ {
    (P1, bold),
    (P2, font_size),
}
```

Aggregate:

```text
ProcessingProfile:
    profile_ref: ProfileRef
    bindings: tuple[RuleBinding, ...]
```

Rules are interpreted only through the frozen Decision Layer. Session never chooses a desired value itself.

### Duplicate/conflict policy

There may be at most one binding per:

```text
(target_class, target_type, aspect_id, property_slot)
```

Duplicate or conflicting bindings are contract errors. Session never resolves rule conflicts by caller order.

Binding input order is not application order.

## 5. Deterministic target enumeration

The session processes the PhysicalIR body story in physical document order.

Paragraph classification order is the frozen `classify_document(...)` order.

Within each paragraph, runs are enumerated recursively in PhysicalIR child order, including supported run containers, yielding only real `run_raw` records.

A run receives class only through `project_run_classification(run, paragraph_result)`.

Only classification results eligible for automatic projection may enter Decision.

No target class is inferred by the session.

## 6. Decision generation

For each eligible classified run and each matching canonical RuleBinding:

```text
DecisionContext(
    DecisionKey(run, aspect_id, property_slot),
    projected TargetClassification,
    ProcessingProfile.profile_ref,
)
```

The observed value comes from frozen `resolve_run_formatting` + `extract_resolved_value`.

The rule is passed to frozen `evaluate_target`.

Session MUST NOT:
- inspect raw OOXML to decide compliance;
- invent desired values;
- reinterpret rule mode;
- downgrade Analysis ambiguity;
- turn an abstained classification into body/heading.

## 7. Canonical binding order

Within the same physical run, matching bindings are ordered canonically by:

```text
(target_class, target_type, aspect_id, property_slot, rule_id, rule.path or "")
```

This makes result/application behavior independent of caller-supplied tuple order.

Document/run order dominates binding order.

## 8. Evaluation snapshot

Each iteration conceptually produces an internal EvaluationSnapshot containing artifacts bound to exactly one current package SHA:

```text
package_sha256
PhysicalIR
StyleCatalog
ClassificationResults
Decisions
OperationPlan
SafetyGateReport
```

This is an internal orchestration structure, not necessarily a public/persisted API.

Artifacts from different package snapshots must never be mixed.

## 9. One patch per iteration

From a compatible SafetyGateReport, the session may execute at most one cleared operation before rebuilding the entire pipeline.

Selection is deterministic:

1. enumerate generated Decisions in physical document order + canonical binding order;
2. map planned operations/tokens by canonical `decision_ref` / `operation_ref`;
3. select the earliest corresponding CLEARED operation that has not already been rejected by Patcher on this exact snapshot;
4. call Patcher once.

OperationPlan's canonical serialization order is explicitly NOT reused as application order.

## 10. Patcher APPLIED

On APPLIED:

1. build exactly one TransformRecord using the bound source Decision;
2. verify TransformRecord input/output hashes against current/new snapshot;
3. append TransformRecord to `transforms` in actual execution order;
4. replace current snapshot with `PatchResult.output_package_bytes`;
5. discard all previous gate tokens and non-final blocked findings;
6. rebuild the full pipeline on the new snapshot.

The source package bytes passed into `process_document` remain immutable.

## 11. Patcher REJECTED

A Patcher rejection is not fatal to independent operations.

For the current exact snapshot, record the rejection keyed by:

```text
(current_package_sha256, operation_ref)
```

and do not retry that exact operation against that unchanged snapshot.

The session may continue with later independent CLEARED operations.

If another operation is APPLIED and the package hash changes, old rejection suppression does not carry into the new snapshot; the whole pipeline is recomputed and a semantically fresh operation may be attempted.

This prevents infinite retry of a document-shape rejection while preserving the possibility that a prior patch legitimately changes the context.

## 12. Gate BLOCKED

Blocked operations are never sent to Patcher.

A blocked operation does not prevent independent CLEARED operations from running in a compatible context.

Global blocked context yields no executable token and therefore no patch for that evaluation snapshot.

Only findings tied to the final output snapshot are returned as final unresolved findings; stale blocked findings from earlier snapshots are discarded after a successful patch.

## 13. Quiescence / completion

A session reaches quiescence when, for the current snapshot, there is no remaining CLEARED operation eligible for attempt.

Two terminal states:

```text
complete
complete_with_findings
```

`complete` means no final deterministic-change Decision remains unapplied in the v0.1 bound slice.

`complete_with_findings` means the session cannot safely make further progress because one or more final deterministic-change operations are blocked or Patcher-rejected, while all safely applicable operations have already been exhausted.

A third terminal state exists only for the explicit operation budget:

```text
operation_limit_reached
```

It is not success and must never be reported as complete.

## 14. Operation budget

Public API accepts:

```text
max_applied_operations: int
```

with a conservative default suitable for documents, proposed `10000`.

Requirements:
- exact int (bool rejected);
- > 0;
- deterministic;
- counts only APPLIED patches / TransformRecords.

If the next patch would exceed the budget, stop without applying it and return `operation_limit_reached` bound to the current snapshot.

No silent truncation.

## 15. Cycle detection

The session maintains the set of package SHA256 values observed after APPLIED patches, starting with the input SHA.

If an APPLIED patch produces an output package SHA already seen in the same session, raise `ProcessingSessionIntegrityError`.

A deterministic profile with unique rule bindings should converge; a package-hash cycle signals an upstream/orchestration contradiction or executor bug and must not be normalized into a successful result.

## 16. Final classifications and Decisions

Before returning any non-exception terminal result, the session evaluates the final/current snapshot and includes:

```text
final_classifications: tuple[ClassificationResult, ...]
final_decisions: tuple[Decision, ...]
```

These are bound by construction to `output_package_sha256`.

Why classifications are retained:
- classification abstention/non-applicability must not disappear silently;
- future Processing Report needs to surface unsupported/ambiguous contexts under the product principle “Na dúvida, marcar.”

Why Decisions are retained:
- no_action/review/preserve/human_choice outcomes matter to later reporting;
- TransformRecords contain only successfully applied changes.

## 17. Final findings

Public minimal finding model:

```text
SessionFinding:
    kind
    decision_ref
    operation_ref | None
    target
    reason
```

Kinds v0.1:

```text
gate_blocked
patch_rejected
operation_limit
```

`reason` is copied from the frozen GateReason / PatchReason vocabulary or a fixed session reason for operation limit. No prose generation here.

Findings are only for the final/current snapshot. Applied history lives exclusively in TransformRecords.

The finding must never embed GateClearedOperation, SafetyGateReport, PatchResult output bytes, or DOCX bytes.

## 18. ProcessingSessionResult

Proposed frozen public result:

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

No timestamp/UUID/hostname.

### Hash invariant

```text
output_package_sha256 == sha256(output_package_bytes)
```

### Transform chain invariant

If transforms is empty:

```text
input_package_sha256 == output_package_sha256
```

If non-empty:

```text
transforms[0].input_package_sha256 == input_package_sha256
transforms[-1].output_package_sha256 == output_package_sha256
```

and for every adjacent pair:

```text
transforms[i].output_package_sha256
==
transforms[i+1].input_package_sha256
```

Order in `transforms` is actual application order and MUST NOT be sorted canonically after execution.

## 19. Public API

Proposed:

```text
process_document(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = 10000,
) -> ProcessingSessionResult
```

No filesystem path; bytes in/bytes out.

No network, clock, randomness, LLM, or global mutable state.

## 20. Error model

```text
ProcessingSessionError
ProcessingSessionContractError
ProcessingSessionIntegrityError
```

ContractError examples:
- wrong input types;
- malformed ProcessingProfile/RuleBinding;
- duplicate binding;
- unsupported binding slot/class/target_type;
- invalid max_applied_operations;
- input DOCX cannot produce a valid PhysicalIR/StyleCatalog under frozen parser contract.

IntegrityError examples:
- artifact binding across snapshots;
- impossible token/Decision ref mismatch;
- TransformRecord lineage mismatch;
- Patcher APPLIED without output bytes/hash invariants;
- repeated package SHA cycle;
- impossible mapping between generated Decision and gate token.

Frozen component exceptions may be wrapped only when preserving their category/cause; never silently downgraded to a normal finding.

## 21. Determinism

Given identical:

```text
package_snapshot bytes
+ ProcessingProfile
+ max_applied_operations
```

session result semantics and output bytes must be deterministic under the supported runtime.

Caller ordering of `ProcessingProfile.bindings` must not affect:
- output DOCX bytes;
- TransformRecord order;
- final Decisions order;
- final findings order.

## 22. Result ordering

- `transforms`: actual application order;
- `final_classifications`: frozen Classification document order;
- `final_decisions`: physical document/run order + canonical binding order;
- `findings`: same final Decision order, with stable kind/reason tie-break only if needed.

No hash/ref sorting is allowed to masquerade as document/application order.

## 23. No user-facing prose yet

Processing Session is orchestration + machine-readable outcome, not final reporting.

It does not generate:
- “corrigido automaticamente” prose;
- highlighted DOCX;
- warning text for end users;
- UI labels.

The next reporting/review layer will consume:
- final classifications;
- final Decisions;
- findings;
- ordered TransformRecords;
- output package bytes.

## 24. Minimum tests before freeze

At minimum:
1. no-change document returns complete with identical bytes/hash and zero transforms;
2. one bold change applies and records one TransformRecord;
3. one font_size change applies and records one TransformRecord;
4. bold + font_size same run apply across two full pipeline reruns;
5. multiple runs are processed in physical document order;
6. caller binding order does not change result/output;
7. multiple paragraphs preserve document application order;
8. after APPLIED, old same-report token is never reused;
9. TransformRecord chain input/output hashes link exactly;
10. final output sha matches bytes;
11. final classifications correspond to final snapshot;
12. classification abstention is retained in final_classifications;
13. final no_action Decisions retained;
14. gate-blocked final op yields complete_with_findings and no Patcher call for it;
15. patch-rejected op is not retried forever on same snapshot;
16. patch rejection does not stop an independent later cleared operation;
17. after another APPLIED patch, rejection suppression is reset for new snapshot;
18. rejected PatchResult never becomes TransformRecord;
19. findings contain no package bytes/tokens;
20. duplicate RuleBinding contract failure;
21. unsupported P3/P4 binding contract failure;
22. unsupported target class failure;
23. bool is rejected as max_applied_operations;
24. zero/negative operation limit rejected;
25. operation limit returns operation_limit_reached without applying beyond budget;
26. cycle detection fail-fast;
27. input bytes object remains unchanged;
28. deterministic repeated output;
29. stable across PYTHONHASHSEED where applicable;
30. runtime contains no filesystem/network/clock/random/LLM access;
31. full existing regression suite preserved;
32. real E2E: body bold + font across at least two runs → final compliant Analysis values + ordered TransformRecords.

## 25. Explicit debts / non-goals

- final user profile schema/validator/UI;
- heading-level-specific rule bindings;
- paragraph P3/P4 execution;
- multi-operation atomic transaction (session remains safe one-patch iterations);
- rollback across already-applied changes;
- persistence/resume after process interruption;
- human-readable Processing Report;
- review/highlight DOCX;
- exception telemetry;
- processing timestamps;
- secondary stories;
- complex-script `w:szCs` correction.

## 26. Audit questions before implementation

Audit especially:
1. whether `ProcessingProfile + RuleBinding` is minimal rather than premature profile architecture;
2. whether final classifications + Decisions + findings + transforms are sufficient for later report/review;
3. whether one-patch-per-full-rerun is correct despite performance cost;
4. whether rejection suppression keyed by `(package_sha, operation_ref)` can hide a legitimate retry;
5. whether actual application order is deterministic and independent of caller binding order;
6. whether final findings only (not stale intermediate findings) is correct reporting semantics;
7. whether operation budget behavior is safe;
8. whether cycle detection should be fail-fast rather than a result status;
9. whether the session should expose SafetyGateReport/PatchResult directly (current proposal: no);
10. whether classification abstentions are adequately preserved for “na dúvida, marcar”.

## 27. Implementation gate

Do not implement until this contract is audited against the frozen public APIs and any discovered mismatch is resolved in this decision.
