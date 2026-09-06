"""SafetyGate v0.1 — final veto layer between OperationPlan and the future patcher.

Contract: docs/decisions/0026-safety-gate-v01-contract.md.

Pipeline:

    OperationPlan + source Decisions + current document context + active
    ProfileRef -> SafetyGateReport

SafetyGate is a VETO, never a new authorization. It never chooses a
`desired_value`, never re-decides compliance, never reclassifies, never
alters a PlannedOperation, never generates XML/patches, never opens or
rewrites DOCX, never uses LLM/heuristics/confidence/risk scores, and never
does IO, network, clock, locale or randomness in the core.

Three failure tiers (blocked is NOT an exception):
1. integrity/contract error -> exception (fail-fast);
2. global blocked context -> the 5 global GateReason values;
3. local blocked operation -> the 6 local GateReason values.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from ..analysis.formatting import (
    resolve_paragraph_formatting,
    resolve_run_formatting,
)
from ..analysis.formatting_model import (
    ANALYSIS_FORMATTING_VERSION,
    STYLES_PART_NAME,
    Length,
    LineSpacing,
    ResolutionStatus,
    StyleCatalog,
)
from ..classification import CLASSIFICATION_VERSION
from ..decision.model import (
    DECISION_VERSION,
    Actionability,
    Decision,
    DecisionKey,
    LineSpacingValue,
    ProfileRef,
)
from ..decision.serialization import serialize_decision
from ..decision.vocabulary import DECISION_VOCABULARY_VERSION, extract_resolved_value
from ..operation_plan.model import (
    PLANNED_STORY_PART,
    LengthValue,
    OperationKind,
    OperationPlan,
    PlannedOperation,
)
from ..operation_plan.planner import decision_ref, source_decisions_hash
from ..operation_plan.serialization import operation_plan_ref, operation_ref
from .model import (
    SAFETY_GATE_VERSION,
    ContextStatus,
    GateClearedOperation,
    GateEvidence,
    GateReason,
    GateResult,
    GateStatus,
    SafetyGateContractError,
    SafetyGateIntegrityError,
    SafetyGateReport,
    _EMISSION_PROOF,
)
from .targets import TARGET_RECORD_TYPES, find_story, paragraph_ancestor, resolve_target

_FONT_SIZE_KEY = DecisionKey("run", "P2", "font_size")


# ---------------------------------------------------------------------------
# Integrity / provenance (tier 1: exceptions, never vetoes)
# ---------------------------------------------------------------------------


def _validate_api_types(
    plan: Any,
    source_decisions: Any,
    current_physical_ir: Any,
    current_style_catalog: Any,
    active_profile_ref: Any,
) -> None:
    if not isinstance(plan, OperationPlan):
        raise SafetyGateContractError("plan must be an OperationPlan")
    if not isinstance(source_decisions, tuple) or not all(
        isinstance(d, Decision) for d in source_decisions
    ):
        raise SafetyGateContractError("source_decisions must be a tuple of Decision")
    if not isinstance(current_physical_ir, Mapping):
        raise SafetyGateContractError(
            "current_physical_ir must be a PhysicalIR mapping produced by the parser"
        )
    if not isinstance(current_style_catalog, StyleCatalog):
        raise SafetyGateContractError("current_style_catalog must be a StyleCatalog")
    if not isinstance(active_profile_ref, ProfileRef):
        raise SafetyGateContractError("active_profile_ref must be a decision ProfileRef")


def _validate_plan_artifact(plan: OperationPlan) -> None:
    """Structural compatibility with the frozen v0.1 stack. No upgrades."""

    if plan.planned_story_part != PLANNED_STORY_PART:
        raise SafetyGateContractError(
            "SafetyGate v0.1 only accepts planned_story_part == word/document.xml"
        )
    for operation in plan.operations:
        if operation.kind is not OperationKind.SET_PROPERTY:
            raise SafetyGateContractError(
                f"unsupported OperationKind for SafetyGate v0.1: {operation.kind!r}"
            )


def _check_source_decisions_integrity(
    plan: OperationPlan, source_decisions: tuple[Decision, ...]
) -> dict[str, Decision]:
    """Hash + duplicate + resolution integrity. Runs before observing the doc."""

    seen: set[bytes] = set()
    for decision in source_decisions:
        blob = serialize_decision(decision)
        if blob in seen:
            raise SafetyGateIntegrityError(
                "duplicate source Decision serialization; refusing to choose one"
            )
        seen.add(blob)

    if source_decisions_hash(source_decisions) != plan.source_decisions_hash:
        raise SafetyGateIntegrityError(
            "source_decisions_hash mismatch: the supplied Decisions are not the "
            "ones the plan was built from"
        )

    by_ref: dict[str, Decision] = {}
    for decision in source_decisions:
        by_ref[decision_ref(decision)] = decision

    for operation in plan.operations:
        if operation.decision_ref not in by_ref:
            raise SafetyGateIntegrityError(
                "planned operation decision_ref resolves to no source Decision"
            )
    return by_ref


def _semantic_equal(key: DecisionKey, operation_value: Any, decision_value: Any) -> bool:
    """Semantic equality with the single frozen font-size type adaptation:

    Decision Decimal("11") <-> Operation LengthValue(Decimal("11"), "pt").
    No other normative transformation is permitted.
    """

    if key == _FONT_SIZE_KEY:
        return (
            isinstance(operation_value, LengthValue)
            and type(decision_value) is Decimal
            and operation_value.unit == "pt"
            and operation_value.value == decision_value
        )
    return type(operation_value) is type(decision_value) and operation_value == decision_value


def _check_operation_decision_binding(operation: PlannedOperation, decision: Decision) -> None:
    """Field-by-field operation <-> source Decision binding (not re-decision)."""

    target = operation.target
    dtarget = decision.target
    for field_name in (
        "target_type",
        "structural_path",
        "physical_hash",
        "target_class",
        "aspect_id",
        "property_slot",
    ):
        if getattr(target, field_name) != getattr(dtarget, field_name):
            raise SafetyGateIntegrityError(
                f"operation/Decision target mismatch on {field_name}"
            )
    key = DecisionKey(dtarget.target_type, dtarget.aspect_id, dtarget.property_slot)
    if operation.key != key:
        raise SafetyGateIntegrityError("operation key does not match the source Decision key")
    if decision.actionability is not Actionability.DETERMINISTIC_CHANGE:
        raise SafetyGateIntegrityError(
            "planned operation bound to a non-deterministic_change Decision"
        )
    if decision.rule_ref is None:
        raise SafetyGateIntegrityError(
            "planned operation bound to a Decision without rule_ref"
        )
    if decision.decision_version != DECISION_VERSION:
        raise SafetyGateIntegrityError(
            f"source Decision decision_version {decision.decision_version!r} is "
            "incompatible with the frozen stack"
        )
    if decision.decision_vocabulary_version != DECISION_VOCABULARY_VERSION:
        raise SafetyGateIntegrityError(
            f"source Decision vocabulary {decision.decision_vocabulary_version!r} is "
            "incompatible with the frozen stack"
        )
    if not _semantic_equal(operation.key, operation.precondition_observed, decision.observed):
        raise SafetyGateIntegrityError(
            "operation precondition_observed does not match the Decision observed value"
        )
    if not _semantic_equal(operation.key, operation.desired_value, decision.desired_value):
        raise SafetyGateIntegrityError(
            "operation desired_value does not match the Decision desired_value"
        )


def _check_profile_homogeneity(
    plan: OperationPlan, source_decisions: tuple[Decision, ...]
) -> ProfileRef | None:
    """One plan = one homogeneous profile; version contract per decision 0026:

    any substantive profile change MUST increment `profile_version`. There is
    no profile content hash in v0.1 (deliberately not invented here).
    """

    profiles = {(d.profile_ref.profile_id, d.profile_ref.profile_version) for d in source_decisions}
    if len(profiles) > 1:
        raise SafetyGateIntegrityError(
            "source Decisions disagree on profile_id/profile_version"
        )
    if not source_decisions:
        return None
    (profile,) = profiles
    expected = plan.upstream_versions
    for decision in source_decisions:
        if decision.decision_version != expected.decision_version:
            raise SafetyGateIntegrityError(
                "source Decision decision_version disagrees with the plan envelope"
            )
        if decision.decision_vocabulary_version != expected.decision_vocabulary_version:
            raise SafetyGateIntegrityError(
                "source Decision vocabulary version disagrees with the plan envelope"
            )
    return ProfileRef(profile_id=profile[0], profile_version=profile[1])


def _check_catalog_binding(
    current_physical_ir: Mapping[str, Any], current_style_catalog: StyleCatalog
) -> None:
    """PhysicalIR <-> StyleCatalog binding (defense in depth).

    v0.1 requires the catalog to be in `part_status == "ok"` and its
    part_sha256 to equal the sha256 of word/styles.xml in the current
    PhysicalIR inventory. A missing/unreadable/foreign catalog is a
    binding/integrity error (fail-fast), never a stale veto and never
    silently degraded inside the gate.
    """

    package = current_physical_ir.get("package")
    if not isinstance(package, Mapping):
        raise SafetyGateContractError("current PhysicalIR lacks a package mapping")
    parts = package.get("parts")
    if not isinstance(parts, (list, tuple)):
        raise SafetyGateContractError("current PhysicalIR package lacks a parts inventory")
    inventory_hashes = {
        part.get("name"): part.get("sha256")
        for part in parts
        if isinstance(part, Mapping)
    }
    inventory_sha = inventory_hashes.get(STYLES_PART_NAME)
    if current_style_catalog.part_status != "ok":
        raise SafetyGateIntegrityError(
            f"StyleCatalog part_status {current_style_catalog.part_status!r} is not "
            "compatible with gating; v0.1 requires an 'ok' styles part binding"
        )
    if (
        inventory_sha is None
        or current_style_catalog.part_sha256 is None
        or current_style_catalog.part_sha256 != inventory_sha
    ):
        raise SafetyGateIntegrityError(
            "StyleCatalog does not belong to the current PhysicalIR "
            f"({STYLES_PART_NAME} identity mismatch)"
        )


def _current_package_sha256(current_physical_ir: Mapping[str, Any]) -> str:
    package = current_physical_ir.get("package")
    if not isinstance(package, Mapping):
        raise SafetyGateContractError("current PhysicalIR lacks a package mapping")
    sha = package.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64:
        raise SafetyGateContractError("current PhysicalIR package.sha256 missing or invalid")
    return sha


# ---------------------------------------------------------------------------
# Global context vetoes (tier 2)
# ---------------------------------------------------------------------------


def _global_veto(
    plan: OperationPlan,
    source_decisions: tuple[Decision, ...],
    current_physical_ir: Mapping[str, Any],
    active_profile_ref: ProfileRef,
    decision_profile_ref: ProfileRef | None,
) -> tuple[GateReason, GateEvidence] | None:
    """First failing global check, in fixed canonical order, or None.

    A single global reason is returned: every blocked GateResult carries
    exactly that reason (report context_reasons mirrors it).
    """

    current_sha = _current_package_sha256(current_physical_ir)
    if current_sha != plan.source_document.package_sha256:
        return GateReason.SOURCE_DOCUMENT_CHANGED, GateEvidence(
            expected=plan.source_document.package_sha256, actual=current_sha
        )
    current_parser_version = current_physical_ir.get("parser_version")
    if not isinstance(current_parser_version, str) or not current_parser_version:
        raise SafetyGateContractError("current PhysicalIR parser_version missing or invalid")
    if current_parser_version != plan.source_document.parser_version:
        return GateReason.PARSER_VERSION_MISMATCH, GateEvidence(
            expected=plan.source_document.parser_version, actual=current_parser_version
        )
    if plan.upstream_versions.analysis_formatting_version != ANALYSIS_FORMATTING_VERSION:
        return GateReason.ANALYSIS_VERSION_MISMATCH, GateEvidence(
            expected=plan.upstream_versions.analysis_formatting_version,
            actual=ANALYSIS_FORMATTING_VERSION,
        )
    # Conservative veto: the gate never reclassifies; the classifier version
    # under which target_class was produced must still be the runtime one.
    if plan.upstream_versions.classification_version != CLASSIFICATION_VERSION:
        return GateReason.CLASSIFICATION_VERSION_MISMATCH, GateEvidence(
            expected=plan.upstream_versions.classification_version,
            actual=CLASSIFICATION_VERSION,
        )
    if decision_profile_ref is not None and decision_profile_ref != active_profile_ref:
        return GateReason.PROFILE_CONTEXT_CHANGED, GateEvidence(
            expected=decision_profile_ref, actual=active_profile_ref
        )
    return None


# ---------------------------------------------------------------------------
# Local per-operation vetoes (tier 3)
# ---------------------------------------------------------------------------


def _current_semantic_value(
    operation: PlannedOperation,
    record: Mapping[str, Any],
    paragraph: Mapping[str, Any] | None,
    catalog: StyleCatalog,
    part: str,
) -> tuple[GateReason, GateEvidence] | tuple[None, Any]:
    """Re-resolve the current semantic value via frozen public Analysis APIs.

    Returns (reason, evidence) for a local veto or (None, value) where value
    is the plan-typed semantic value (bool / LengthValue / LineSpacingValue /
    str token). Raw OOXML (half-points, w:sz, twips) is never consulted;
    `canonical_xml` is never used to derive semantic values.
    """

    key = operation.key
    if key.target_type == "run":
        analysis = resolve_run_formatting(record, paragraph, catalog, part)
    else:
        analysis = resolve_paragraph_formatting(record, catalog, part)
    resolved = extract_resolved_value(key, analysis)
    if resolved.status is not ResolutionStatus.RESOLVED:
        # Expected non-resolved Analysis outcome -> local veto, no exception.
        return (
            GateReason.CURRENT_VALUE_UNAVAILABLE,
            GateEvidence(
                expected=operation.precondition_observed,
                actual=f"analysis_status:{resolved.status.value}",
            ),
        )
    value = resolved.value
    if key.property_slot == "bold":
        if not isinstance(value, bool):
            return (
                GateReason.CURRENT_VALUE_UNAVAILABLE,
                GateEvidence(
                    expected=operation.precondition_observed,
                    actual=f"analysis_status:{ResolutionStatus.INVALID.value}",
                ),
            )
        return None, value
    if key.property_slot == "font_size":
        if not isinstance(value, Length) or value.unit != "pt":
            return (
                GateReason.CURRENT_VALUE_UNAVAILABLE,
                GateEvidence(
                    expected=operation.precondition_observed,
                    actual=f"analysis_status:{ResolutionStatus.INVALID.value}",
                ),
            )
        return None, LengthValue(value=value.value, unit="pt")
    if key.property_slot == "spacing.line":
        if not isinstance(value, LineSpacing):
            return (
                GateReason.CURRENT_VALUE_UNAVAILABLE,
                GateEvidence(
                    expected=operation.precondition_observed,
                    actual=f"analysis_status:{ResolutionStatus.INVALID.value}",
                ),
            )
        # Only semantic (rule, value, unit) participate; raw forensic fields
        # of Analysis LineSpacing are ignored, mirroring the frozen Decision.
        return None, LineSpacingValue(rule=value.rule, value=value.value, unit=value.unit)
    if key.property_slot == "alignment":
        if not isinstance(value, str):
            return (
                GateReason.CURRENT_VALUE_UNAVAILABLE,
                GateEvidence(
                    expected=operation.precondition_observed,
                    actual=f"analysis_status:{ResolutionStatus.INVALID.value}",
                ),
            )
        return None, value
    raise SafetyGateContractError(f"unsupported property slot for SafetyGate v0.1: {key}")


def _gate_operation_local(
    operation: PlannedOperation,
    story: Mapping[str, Any],
    catalog: StyleCatalog,
    part: str,
) -> tuple[GateResult, PlannedOperation | None]:
    """Gate one operation against the current story. Never raises for stale
    content; raises only on contract/integrity failures of the inputs."""

    op_ref = operation_ref(operation)
    target = operation.target

    matches = resolve_target(story, target.structural_path)
    if not matches:
        return GateResult(
            operation_ref=op_ref,
            status=GateStatus.BLOCKED,
            reasons=(GateReason.TARGET_NOT_FOUND,),
            evidence=GateEvidence(expected=target.structural_path),
        ), None
    if len(matches) > 1:
        return GateResult(
            operation_ref=op_ref,
            status=GateStatus.BLOCKED,
            reasons=(GateReason.TARGET_NOT_UNIQUE,),
            evidence=GateEvidence(expected=target.structural_path, actual=len(matches)),
        ), None

    record, ancestors = matches[0]
    expected_types = TARGET_RECORD_TYPES.get(target.target_type)
    if expected_types is None:
        raise SafetyGateContractError(
            f"unknown target_type for SafetyGate v0.1: {target.target_type!r}"
        )
    if record.get("source_type") not in expected_types:
        return GateResult(
            operation_ref=op_ref,
            status=GateStatus.BLOCKED,
            reasons=(GateReason.TARGET_TYPE_MISMATCH,),
            evidence=GateEvidence(
                expected=target.target_type, actual=record.get("source_type")
            ),
        ), None

    paragraph = None
    if target.target_type == "run":
        paragraph = paragraph_ancestor(ancestors)
        if paragraph is None:
            # Documented vocabulary choice (decision 0026): a run target
            # without a real paragraph ancestor in the same story is reported
            # as target_not_found — the required paragraph context was not
            # found. No new reason is introduced in v0.1.
            return GateResult(
                operation_ref=op_ref,
                status=GateStatus.BLOCKED,
                reasons=(GateReason.TARGET_NOT_FOUND,),
                evidence=GateEvidence(
                    expected=f"paragraph ancestor of {target.structural_path}"
                ),
            ), None

    current_hash = record.get("physical_hash")
    if not isinstance(current_hash, str):
        raise SafetyGateContractError("located record lacks a physical_hash")
    if current_hash != target.physical_hash:
        return GateResult(
            operation_ref=op_ref,
            status=GateStatus.BLOCKED,
            reasons=(GateReason.PHYSICAL_HASH_MISMATCH,),
            evidence=GateEvidence(expected=target.physical_hash, actual=current_hash),
        ), None

    reason_or_none, value_or_evidence = _current_semantic_value(
        operation, record, paragraph, catalog, part
    )
    if reason_or_none is not None:
        return GateResult(
            operation_ref=op_ref,
            status=GateStatus.BLOCKED,
            reasons=(reason_or_none,),
            evidence=value_or_evidence,
        ), None

    current_semantic = value_or_evidence
    # Compare-and-set: the planned precondition must still hold exactly.
    # current == desired (but != precondition) is still precondition_mismatch
    # (the plan is stale); the gate never re-plans and never emits no_action.
    if current_semantic != operation.precondition_observed:
        return GateResult(
            operation_ref=op_ref,
            status=GateStatus.BLOCKED,
            reasons=(GateReason.PRECONDITION_MISMATCH,),
            evidence=GateEvidence(
                expected=operation.precondition_observed, actual=current_semantic
            ),
        ), None

    return GateResult(
        operation_ref=op_ref,
        status=GateStatus.CLEARED,
        reasons=(),
        evidence=GateEvidence(current_observed=current_semantic),
    ), operation


# ---------------------------------------------------------------------------
# Public orchestration API
# ---------------------------------------------------------------------------


def evaluate_operation_plan(
    plan: OperationPlan,
    source_decisions: tuple[Decision, ...],
    current_physical_ir: Mapping[str, Any],
    current_style_catalog: StyleCatalog,
    active_profile_ref: ProfileRef,
) -> SafetyGateReport:
    """Authoritative plan-level SafetyGate v0.1 evaluation.

    Receives the CURRENT PhysicalIR (already parsed; the gate never opens
    files nor re-parses), the CURRENT StyleCatalog derived from the SAME
    package bytes (never precomputed AnalysisViews), and the active
    ProfileRef. Current semantic state is derived internally through frozen
    public Analysis APIs.

    TOCTOU contract: the report and every GateClearedOperation carry
    `current_package_sha256`. The future patcher MUST operate on the exact
    same immutable package snapshot whose PhysicalIR/StyleCatalog were gated
    (or recompute the package bytes hash immediately before mutation and
    require equality). Gating bytes A and patching bytes B without
    revalidation is prohibited.
    """

    _validate_api_types(
        plan, source_decisions, current_physical_ir, current_style_catalog, active_profile_ref
    )
    _validate_plan_artifact(plan)
    _check_catalog_binding(current_physical_ir, current_style_catalog)

    plan_ref = operation_plan_ref(plan)
    current_sha = _current_package_sha256(current_physical_ir)

    by_ref = _check_source_decisions_integrity(plan, source_decisions)
    for operation in plan.operations:
        _check_operation_decision_binding(operation, by_ref[operation.decision_ref])
    decision_profile_ref = _check_profile_homogeneity(plan, source_decisions)

    global_veto = _global_veto(
        plan, source_decisions, current_physical_ir, active_profile_ref, decision_profile_ref
    )

    if global_veto is not None:
        reason, evidence = global_veto
        # Full audit trail: one blocked GateResult per planned operation, all
        # carrying the same global reason; no local checks are executed.
        results = tuple(
            GateResult(
                operation_ref=operation_ref(operation),
                status=GateStatus.BLOCKED,
                reasons=(reason,),
                evidence=evidence,
            )
            for operation in plan.operations
        )
        return SafetyGateReport(
            safety_gate_version=SAFETY_GATE_VERSION,
            operation_plan_ref=plan_ref,
            current_package_sha256=current_sha,
            context_status=ContextStatus.BLOCKED,
            context_reasons=(reason,),
            results=results,
            cleared_operations=(),
        )

    story = find_story(current_physical_ir, plan.planned_story_part)

    results: list[GateResult] = []
    cleared: list[GateClearedOperation] = []
    for operation in plan.operations:
        result, cleared_operation = _gate_operation_local(
            operation, story, current_style_catalog, plan.planned_story_part
        )
        results.append(result)
        if cleared_operation is not None:
            cleared.append(
                GateClearedOperation(
                    operation=cleared_operation,
                    operation_ref=result.operation_ref,
                    operation_plan_ref=plan_ref,
                    current_package_sha256=current_sha,
                    _proof=_EMISSION_PROOF,
                )
            )

    return SafetyGateReport(
        safety_gate_version=SAFETY_GATE_VERSION,
        operation_plan_ref=plan_ref,
        current_package_sha256=current_sha,
        context_status=ContextStatus.COMPATIBLE,
        context_reasons=(),
        results=tuple(results),
        cleared_operations=tuple(cleared),
    )


def gate_operation(
    operation: PlannedOperation,
    decision: Decision,
    current_physical_ir: Mapping[str, Any],
    current_style_catalog: StyleCatalog,
) -> GateResult:
    """Unit-level local gate for a single operation (local vetoes only).

    Integrity binding to the source Decision is still enforced; global
    context checks are NOT performed here — `evaluate_operation_plan` is the
    authoritative orchestration API. Intended for controlled local-veto
    tests where a real package mismatch would mask the intended local veto.
    """

    if not isinstance(operation, PlannedOperation):
        raise SafetyGateContractError("operation must be a PlannedOperation")
    if not isinstance(decision, Decision):
        raise SafetyGateContractError("decision must be a Decision")
    if operation.decision_ref != decision_ref(decision):
        raise SafetyGateIntegrityError(
            "operation decision_ref does not resolve to the supplied Decision"
        )
    _check_operation_decision_binding(operation, decision)
    _check_catalog_binding(current_physical_ir, current_style_catalog)
    story = find_story(current_physical_ir, PLANNED_STORY_PART)
    result, _ = _gate_operation_local(
        operation, story, current_style_catalog, PLANNED_STORY_PART
    )
    return result
