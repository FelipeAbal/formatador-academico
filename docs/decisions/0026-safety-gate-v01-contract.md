# Decision 0026 — SafetyGate v0.1 Contract

Status: APPROVED FOR IMPLEMENTATION

## Context

OperationPlan v0.1 is frozen in 0025. The next layer must prevent a planned operation from reaching the future patcher when the current execution context no longer matches the state against which the plan was produced.

Pipeline:

```text
OperationPlan
-> SafetyGate
-> future XML patch/applicator
```

Principle:

**OperationPlan proposes; SafetyGate vetoes or clears; patcher executes.**

`cleared` means only that no SafetyGate veto fired against the current observed state. It is not a new normative authorization and does not revalidate the correctness of the profile, classification, or rule semantics.

## Boundary

SafetyGate MUST NOT:
- re-decide compliance;
- choose or alter desired values;
- change profile/rule/classification;
- mutate OperationPlan or Decisions;
- read raw OOXML/canonical_xml to resolve semantic properties;
- modify DOCX/XML;
- generate or apply patches;
- use LLMs, heuristics, risk scores, randomness, clock, locale, network, or filesystem IO in the core.

SafetyGate revalidates only current applicability and integrity.

## Public API target

```text
evaluate_operation_plan(
    plan: OperationPlan,
    source_decisions: tuple[Decision, ...],
    current_physical_ir,
    current_style_catalog: StyleCatalog,
    active_profile_ref: ProfileRef,
) -> SafetyGateReport
```

An internal/unit-level `gate_operation(...)` helper may be exposed if useful for local-veto tests, but plan-level evaluation is the authoritative orchestration API.

SafetyGate receives current PhysicalIR + current StyleCatalog, never precomputed AnalysisViews. Current semantic state is derived internally through frozen public Analysis APIs.

## Required current context

Runtime context is:
- current PhysicalIR freshly derived from the package snapshot intended for mutation;
- current StyleCatalog derived from the SAME package bytes;
- current active ProfileRef.

PhysicalIR remains runtime input, not a frozen serializable model embedded in the report.

## Source Decisions are mandatory

The complete source Decision tuple used to build the OperationPlan is required.

Before any runtime veto checks, SafetyGate must verify:
- recomputed canonical source-decisions hash equals `plan.source_decisions_hash`;
- every PlannedOperation `decision_ref` resolves to exactly one source Decision;
- duplicate serialized Decisions are an integrity error;
- operation target equals source Decision target;
- operation key equals source Decision key;
- operation precondition equals Decision observed value, allowing only the frozen semantic type adaptation for font size;
- operation desired value equals Decision desired value, with the same permitted type adaptation;
- source Decision remains `deterministic_change`;
- source Decision has `rule_ref != None`.

These are provenance/integrity checks, not re-decision.

## Active profile

`active_profile_ref: ProfileRef` is mandatory.

The plan already requires one homogeneous `profile_id/profile_version`. SafetyGate revalidates that the active profile equals the profile referenced by the source Decisions.

Profile mismatch is a GLOBAL runtime veto: `profile_context_changed`.

No profile-content fingerprint exists in v0.1. Contract: any substantive profile change MUST increment `profile_version`.

## Three required stale/drift checks

An operation may be cleared only if all applicable checks still hold:

1. source package identity;
2. physical target identity;
3. semantic precondition.

### Package fingerprint

Compare:

```text
current_physical_ir.package.sha256
==
plan.source_document.package_sha256
```

Mismatch is a GLOBAL veto `source_document_changed` and blocks every operation.

Byte-level ZIP differences are intentionally conservative in v0.1. No semantic package equivalence is attempted.

### Parser version

Current PhysicalIR parser version must equal `plan.source_document.parser_version`.

Mismatch is GLOBAL `parser_version_mismatch`.

### Planned story part

v0.1 accepts only:

```text
word/document.xml
```

A plan carrying another story part is an integrity/contract error, not a runtime local veto.

### Target resolution

Locate the current target in the main body story using:
- planned story part;
- structural_path;
- target_type.

Resolution must yield exactly one target.

Local vetoes:
- zero match -> `target_not_found`;
- multiple matches -> `target_not_unique`;
- located physical record incompatible with target_type -> `target_type_mismatch`.

For run targets, parent paragraph context must be obtained through the actual PhysicalIR tree/ancestry, not string-prefix path inference. Run analysis with the wrong paragraph is prohibited.

### Physical target hash

After locating the target:

```text
current_target.physical_hash
==
operation.target.physical_hash
```

Mismatch is LOCAL `physical_hash_mismatch`.

The gate does not recalculate the physical hash; it consumes the current PhysicalIR value.

### Semantic precondition

Current semantic state is re-resolved via frozen Analysis APIs and compared against `precondition_observed`.

Supported v0.1 properties:
- P1/run/bold;
- P2/run/font_size;
- P3/paragraph/spacing.line;
- P4/paragraph/alignment.

The gate does not inspect raw OOXML values such as half-points/twips.

Comparison rules:
- bold: bool equality;
- font size: Analysis `Length(value, unit)` vs plan `LengthValue(value, unit)` by `(value, unit)`;
- spacing.line: Analysis `LineSpacing(rule, value, unit, raw_*)` vs Decision/Plan `LineSpacingValue(rule, value, unit)` by semantic `(rule, value, unit)` only; raw forensic fields do not participate;
- alignment: canonical token equality.

If current Analysis status is absent/unresolved/invalid/ambiguous -> LOCAL `current_value_unavailable`.

If current semantic value differs from the planned precondition -> LOCAL `precondition_mismatch`.

This includes:
- current equals desired but no longer equals precondition;
- current differs from both precondition and desired.

SafetyGate never turns a stale operation into no_action and never re-plans.

## PhysicalIR ↔ StyleCatalog binding

The current code already exposes enough binding information; no upstream redesign is required.

SafetyGate must verify that current StyleCatalog belongs to current PhysicalIR by checking the styles part identity/status, including:

```text
current_style_catalog.part_sha256
==
current_physical_ir inventory["word/styles.xml"].sha256
```

and the expected successful part status.

A PhysicalIR/StyleCatalog A/B mismatch is an INTEGRITY/BINDING ERROR (exception), not a stale-document veto.

The orchestrator must derive both from the same package bytes; SafetyGate rechecks this as defense in depth.

## Current Analysis derivation

SafetyGate derives semantic current state internally from current PhysicalIR + bound StyleCatalog via existing frozen Analysis functions.

It must not accept arbitrary externally prepared AnalysisViews because that would permit cross-document binding errors.

Expected/non-resolved Analysis outcomes become local vetoes. Unexpected exceptions from Analysis are fail-fast programming/contract failures, not a synthetic `evaluation_error` GateReason.

## Runtime version checks

`decision_version` and `decision_vocabulary_version` remain bound to source Decisions and are integrity checked.

`analysis_formatting_version` and `classification_version` remain orchestrator assertions in OperationPlan v0.1, not cryptographically bound provenance.

Nevertheless the SafetyGate conservatively compares the plan values to the current runtime constants:
- Analysis version mismatch -> GLOBAL `analysis_version_mismatch`;
- Classification version mismatch -> GLOBAL `classification_version_mismatch`.

Analysis mismatch is mandatory because SafetyGate reuses Analysis semantics. Classification mismatch is conservative because target_class was produced under that classifier version. This classification veto may be relaxed in a future version with stronger pipeline-context binding.

## Global vs local vetoes

### Global veto reasons

Closed v0.1 vocabulary:
- `source_document_changed`;
- `parser_version_mismatch`;
- `analysis_version_mismatch`;
- `classification_version_mismatch`;
- `profile_context_changed`.

A global veto sets report context to blocked and no operation is cleared.

For audit completeness, every operation in the plan still receives a blocked GateResult carrying the global reason.

### Local veto reasons

Closed v0.1 vocabulary:
- `target_not_found`;
- `target_not_unique`;
- `target_type_mismatch`;
- `physical_hash_mismatch`;
- `current_value_unavailable`;
- `precondition_mismatch`.

Local vetoes affect only the operation concerned when the global context is compatible.

Partial clearance is valid.

## Status vocabulary

```text
GateStatus:
    cleared
    blocked

ContextStatus:
    compatible
    blocked
```

Do not use `safe`, `authorized`, `approved`, numeric confidence, or risk score.

No independent reason-vocabulary version is introduced in v0.1. Gate reasons are frozen under:

```text
SAFETY_GATE_VERSION = "0.1"
```

Any incompatible reason-semantic change requires a SafetyGate version bump.

## Deterministic references

The gate introduces derived references, not UUIDs:

```text
operation_plan_ref = sha256(serialize_operation_plan(plan))
operation_ref = sha256(canonical serialize of PlannedOperation)
```

OperationPlan code must expose additive public canonical helpers needed by SafetyGate rather than duplicating private hash/serialization logic. This is an additive internal dependency and does not reopen freeze 0025.

## GateEvidence

Reason and evidence are separate.

Evidence is minimal and factual, sufficient for technical reporting/TransformLog. It may carry the expected/actual values relevant to the check that failed, such as:
- expected/actual package sha;
- expected/actual target hash;
- expected precondition/current observed semantic value.

Current semantic values use existing frozen semantic types; no OOXML representation is introduced.

Presentation layers may later suppress technical hashes from user-facing reports.

## GateResult

Target model:

```text
GateResult:
    operation_ref
    status: GateStatus
    reasons: tuple[GateReason, ...]
    evidence: GateEvidence | None
```

In v0.1 a result normally carries exactly one veto reason when blocked and no reason when cleared.

GateResult does not embed the full PlannedOperation.

## SafetyGateReport

Target model:

```text
SafetyGateReport:
    safety_gate_version
    operation_plan_ref
    current_package_sha256
    context_status
    context_reasons
    results
    cleared_operations
```

`results` are ordered exactly according to canonical `plan.operations` order.

`cleared_operations` contains the typed execution-boundary objects described below.

An empty OperationPlan produces a valid report with empty results/cleared operations. Context is still evaluated and recorded.

## GateClearedOperation — mandatory typed boundary

SafetyGate v0.1 introduces a frozen execution token:

```text
GateClearedOperation:
    operation: PlannedOperation
    operation_ref
    operation_plan_ref
    current_package_sha256
```

The embedded PlannedOperation is field/byte-equivalent to the input operation. SafetyGate must not normalize or alter it.

`GateClearedOperation` means only that no gate veto fired against the observed state.

Future patchers MUST accept `GateClearedOperation`, never raw `PlannedOperation`.

This typed boundary is mandatory to make SafetyGate bypass structurally difficult.

## TOCTOU / snapshot identity

Gate→patch race must be addressed by design before any patcher is allowed.

The gate evaluates a package snapshot identified by `current_package_sha256`.

Both SafetyGateReport and GateClearedOperation carry that identity.

Future patcher contract MUST either:
1. operate on the exact immutable OriginalPackage/package snapshot from which current PhysicalIR/StyleCatalog were derived; or
2. recompute the package bytes hash immediately before mutation and require equality with `GateClearedOperation.current_package_sha256`.

A patcher must never gate one snapshot and then silently reopen/apply to another file state.

SafetyGate v0.1 does not need the package bytes themselves; identity is sufficient for this layer. The full execution envelope can be introduced with the patcher.

## Error model

Three tiers:

### 1. Exception / integrity error
Examples:
- malformed/incompatible plan artifact;
- source_decisions_hash mismatch;
- duplicate source Decision serialization;
- missing/ambiguous source Decision for operation;
- operation↔Decision binding mismatch;
- source Decision not deterministic_change;
- missing rule_ref for planned operation;
- unsupported/incompatible OperationKind/version;
- invalid planned_story_part;
- PhysicalIR↔StyleCatalog binding mismatch;
- unexpected Analysis/programming exception.

### 2. Global blocked context
The plan is internally valid, but the current global context changed. Reasons are the 5 global reasons above.

### 3. Local blocked operation
Global context is compatible, but the specific current target/precondition fails one of the 6 local checks.

A local target failure never crashes unrelated operations.

## Determinism and immutability

SafetyGate models are frozen.
Use tuples, not mutable lists/dicts, in serialized public artifacts.

Canonical serialization follows existing project conventions:
- enums -> strings;
- Decimal -> strings;
- tuples -> arrays;
- sort_keys;
- compact separators;
- UTF-8;
- no timestamps/random values.

Same logical inputs must produce byte-identical reports regardless of source Decision caller order or PYTHONHASHSEED.

## First executable slice

No patching yet.

Required E2E:

```text
DOCX
-> Parser
-> Analysis
-> Classification
-> Decision
-> OperationPlan
-> SafetyGate
```

For the existing synthetic body scenario:
- bold true -> false planned operation -> cleared when unchanged;
- font 11pt -> 12pt planned operation -> cleared when unchanged;
- spacing/alignment remain upstream skipped and are not gate operations;
- context_status=compatible;
- exactly 2 cleared operations.

## Minimum implementation tests

At least:
1. unchanged bold -> cleared;
2. unchanged font -> cleared;
3. package mismatch -> global block;
4. parser version mismatch -> global block;
5. analysis version mismatch -> global block;
6. classification version mismatch -> global block;
7. profile mismatch -> global block;
8. physical hash mismatch -> local block;
9. target not found -> local block;
10. target not unique -> local block;
11. target type mismatch -> local block;
12. Analysis unresolved/absent/invalid/ambiguous -> local block;
13. precondition mismatch -> local block;
14. current == desired but precondition differs -> local block;
15. one operation cleared + one blocked -> partial clearance;
16. source_decisions_hash mismatch -> integrity error;
17. missing source Decision -> integrity error;
18. operation↔Decision mismatch -> integrity error;
19. PhysicalIR A + StyleCatalog B -> binding error;
20. run under run_container with correct paragraph ancestor -> correct semantic evaluation;
21. active profile version changed -> global block;
22. empty plan -> deterministic valid report;
23. deterministic serialization;
24. cross-order source Decisions -> byte-identical report;
25. hashseed/process determinism;
26. immutable models / inputs not mutated;
27. E2E DOCX -> SafetyGate with 2 cleared operations.

Local drift/precondition tests may use controlled unit contexts so the global package mismatch does not mask the intended local veto. Real E2E package checking must never be weakened for testing.

## Dependencies before implementation

Before/with SafetyGate implementation, add public canonical helpers in operation_plan for:
- canonical PlannedOperation serialization;
- operation_ref;
- operation_plan_ref;
- canonical source_decisions_hash / decision_ref reuse as needed.

These helpers must delegate to/centralize existing canonical logic and must not create a parallel serialization scheme.

## Deferred, non-blocking

- semantic equivalence for byte-different re-packed DOCX;
- stronger cryptographic pipeline-context hash for analysis/classification provenance;
- secondary-story execution;
- document/application ordering beyond canonical deterministic ordering;
- TransformLog;
- full execution snapshot envelope beyond the SHA identity already frozen here.

## Decision

SafetyGate v0.1 contract is approved for implementation.

No upstream architectural expansion is required before the first slice.

Implementation must preserve the 389 frozen tests and undergo adversarial audit before merge/freeze.
