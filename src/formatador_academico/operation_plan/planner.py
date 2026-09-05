"""OperationPlan v0.1 planner — pure Decision -> PlanningResult transformation.

Contract: docs/decisions/0024-operation-plan-v01-contract.md.

The planner never re-decides compliance, never consults profile/rule to
choose values, never touches DOCX/XML/parser/Analysis/SafetyGate, and never
uses IO/LLM/random/clock/locale. `actionability` is the sole authority for
whether a mutation is planned; `reason` is carried only as provenance.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from ..decision.model import (
    DECISION_VERSION,
    Actionability,
    Decision,
    DecisionKey,
    LineSpacingValue,
)
from ..decision.serialization import serialize_decision
from ..decision.vocabulary import DECISION_VOCABULARY_VERSION, SUPPORTED_KEYS, vocabulary_entry
from .model import (
    PLANNED_STORY_PART,
    LengthValue,
    OperationKind,
    OperationPlan,
    OperationTarget,
    PlannedOperation,
    PlanningResult,
    PlanningStatus,
    SourceDocumentRef,
    UpstreamVersions,
    _SHA256_RE,
    _operation_sort_key,
)


class OperationPlanError(Exception):
    """Base class for OperationPlan failures."""


class OperationPlanContractError(OperationPlanError, ValueError):
    """A Decision (or envelope input) violates the contract. Fail-fast."""


class OperationPlanAggregationError(OperationPlanError, ValueError):
    """Cross-Decision integrity failure (conflict/duplicate/heterogeneity)."""


_EXECUTABLE_KEYS = frozenset(SUPPORTED_KEYS)

# Value typing per executable slot (semantic, never OOXML).
_SLOT_VALUE_TYPES = {
    DecisionKey("run", "P1", "bold"): bool,
    DecisionKey("run", "P2", "font_size"): Decimal,
    DecisionKey("paragraph", "P3", "spacing.line"): LineSpacingValue,
    DecisionKey("paragraph", "P4", "alignment"): str,
}

_SKIPPED_ACTIONABILITIES = frozenset(
    {
        Actionability.NO_ACTION,
        Actionability.HUMAN_CHOICE,
        Actionability.REVIEW,
        Actionability.PRESERVE,
    }
)


def _decision_ref(decision: Decision) -> str:
    """sha256 over the canonical frozen Decision serialization. No UUIDs."""

    return hashlib.sha256(serialize_decision(decision)).hexdigest()


def _decision_key(decision: Decision) -> DecisionKey:
    target = decision.target
    return DecisionKey(target.target_type, target.aspect_id, target.property_slot)


def _convert_value(key: DecisionKey, value: Any) -> Any:
    """Materialize plan-typed semantic values. font_size gains explicit unit."""

    if key == DecisionKey("run", "P2", "font_size"):
        return LengthValue(value=value, unit="pt")
    return value


def _validate_deterministic_contract(decision: Decision) -> None:
    """Fail-fast on internally contradictory deterministic_change Decisions."""

    if decision.observed is None:
        raise OperationPlanContractError(
            "deterministic_change requires observed != None"
        )
    if decision.desired_value is None:
        raise OperationPlanContractError(
            "deterministic_change requires desired_value != None"
        )
    if decision.observed == decision.desired_value:
        raise OperationPlanContractError(
            "deterministic_change with observed == desired is an upstream contradiction"
        )
    if decision.rule_ref is None:
        raise OperationPlanContractError(
            "deterministic_change requires rule_ref != None; authorization is never invented"
        )


def _validate_value_type(key: DecisionKey, decision: Decision) -> None:
    expected = _SLOT_VALUE_TYPES[key]
    for label, value in (("observed", decision.observed), ("desired_value", decision.desired_value)):
        # bool is a subclass of int; exact-type check keeps the contract tight.
        if type(value) is not expected:
            raise OperationPlanContractError(
                f"{key.aspect_id}/{key.property_slot} requires {expected.__name__} "
                f"for {label}, got {type(value).__name__}"
            )


def plan_decision(decision: Decision) -> PlanningResult:
    """Plan a single Decision. Never returns None for a valid Decision.

    - deterministic_change + supported slot -> planned + PlannedOperation
    - no_action | human_choice | review | preserve -> skipped, no operation
    - deterministic_change + known-but-unsupported slot -> unsupported

    Contract violations raise OperationPlanContractError; they are never
    downgraded to skipped.
    """

    if not isinstance(decision, Decision):
        raise OperationPlanContractError("plan_decision expects a Decision")
    if not isinstance(decision.actionability, Actionability):
        raise OperationPlanContractError("decision.actionability must be Actionability")
    if decision.decision_version != DECISION_VERSION:
        raise OperationPlanContractError(
            f"planner v0.1 only accepts decision_version == {DECISION_VERSION!r}"
        )
    if decision.decision_vocabulary_version != DECISION_VOCABULARY_VERSION:
        raise OperationPlanContractError(
            "planner v0.1 only accepts decision_vocabulary_version == "
            f"{DECISION_VOCABULARY_VERSION!r}"
        )
    target = decision.target
    if not target.structural_path:
        raise OperationPlanContractError("decision target structural_path must be non-empty")
    # physical_hash is the physical fingerprint the future SafetyGate relies
    # on; the parser always produces a lowercase sha256 hex digest.
    if not isinstance(target.physical_hash, str) or not _SHA256_RE.match(target.physical_hash):
        raise OperationPlanContractError(
            "decision target physical_hash must be 64 lowercase hex chars"
        )
    if not isinstance(target.target_class, str) or not target.target_class:
        raise OperationPlanContractError("decision target target_class must be non-empty")

    key = _decision_key(decision)
    try:
        vocabulary_entry(key)
    except ValueError as exc:
        raise OperationPlanContractError(
            f"decision key outside Decision Vocabulary v{DECISION_VOCABULARY_VERSION}: {key}"
        ) from exc

    ref = _decision_ref(decision)
    provenance = {
        "decision_ref": ref,
        "decision_actionability": decision.actionability.value,
        "decision_reason": decision.reason.value,
    }

    if decision.actionability in _SKIPPED_ACTIONABILITIES:
        return PlanningResult(status=PlanningStatus.SKIPPED, operation=None, **provenance)

    if decision.actionability is not Actionability.DETERMINISTIC_CHANGE:
        raise OperationPlanContractError(
            f"unknown actionability: {decision.actionability!r}"
        )

    # deterministic_change: contract first, then slot support.
    _validate_deterministic_contract(decision)

    if key not in _EXECUTABLE_KEYS:
        return PlanningResult(status=PlanningStatus.UNSUPPORTED, operation=None, **provenance)

    _validate_value_type(key, decision)

    operation_target = OperationTarget(
        target_type=target.target_type,
        structural_path=target.structural_path,
        physical_hash=target.physical_hash,
        target_class=target.target_class,
        aspect_id=target.aspect_id,
        property_slot=target.property_slot,
    )
    operation = PlannedOperation(
        kind=OperationKind.SET_PROPERTY,
        key=key,
        target=operation_target,
        precondition_observed=_convert_value(key, decision.observed),
        desired_value=_convert_value(key, decision.desired_value),
        decision_ref=ref,
    )
    return PlanningResult(status=PlanningStatus.PLANNED, operation=operation, **provenance)


def _decision_hash_sort_key(decision: Decision) -> tuple[str, ...]:
    """Total deterministic key so source_decisions_hash never depends on the
    caller's arbitrary order. This is NOT document order."""

    target = decision.target
    return (
        target.target_type,
        target.structural_path,
        target.physical_hash,
        target.aspect_id,
        target.property_slot,
        serialize_decision(decision).decode("utf-8"),
    )


def _source_decisions_hash(decisions: tuple[Decision, ...]) -> str:
    """sha256 over a canonical JSON array of the canonically serialized
    Decisions, deterministically ordered. Framing via JSON array (no ambiguous
    plain concatenation)."""

    ordered = sorted(decisions, key=_decision_hash_sort_key)
    payload = json.dumps(
        [serialize_decision(decision).decode("utf-8") for decision in ordered],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_homogeneity(
    decisions: tuple[Decision, ...], upstream_versions: UpstreamVersions
) -> None:
    """One plan = one decision stack + one active profile (v0.1)."""

    versions = {(d.decision_version, d.decision_vocabulary_version) for d in decisions}
    if len(versions) > 1:
        raise OperationPlanAggregationError(
            "decisions disagree on decision_version/decision_vocabulary_version"
        )
    if decisions:
        (decision_version, vocabulary_version), = versions
        if upstream_versions.decision_version != decision_version:
            raise OperationPlanAggregationError(
                "upstream_versions.decision_version does not match the decisions"
            )
        if upstream_versions.decision_vocabulary_version != vocabulary_version:
            raise OperationPlanAggregationError(
                "upstream_versions.decision_vocabulary_version does not match the decisions"
            )
        profiles = {(d.profile_ref.profile_id, d.profile_ref.profile_version) for d in decisions}
        if len(profiles) > 1:
            raise OperationPlanAggregationError(
                "v0.1 does not allow mixing profile_id/profile_version in one plan"
            )


def _validate_no_duplicates_or_conflicts(operations: tuple[PlannedOperation, ...]) -> None:
    """Same target + same key from distinct Decisions is an upstream bug:

    - identical observed+desired -> duplicate error (never deduplicate);
    - different observed or desired -> conflict error (never pick by order).
    """

    by_identity: dict[tuple[Any, ...], PlannedOperation] = {}
    for operation in operations:
        # Identity = physical target + property slot. `target_class` is
        # deliberately EXCLUDED: two Decisions addressing the same physical
        # target and slot with divergent target_class are an upstream
        # contradiction, not two distinct targets — allowing both would
        # produce two independent mutations over the same physical slot.
        identity = (
            operation.target.target_type,
            operation.target.structural_path,
            operation.target.physical_hash,
            operation.target.aspect_id,
            operation.target.property_slot,
        )
        existing = by_identity.get(identity)
        if existing is None:
            by_identity[identity] = operation
            continue
        same = (
            existing.precondition_observed == operation.precondition_observed
            and existing.desired_value == operation.desired_value
        )
        if same:
            raise OperationPlanAggregationError(
                f"duplicate operation for target {identity}; refusing to deduplicate"
            )
        raise OperationPlanAggregationError(
            f"conflicting operations for target {identity}; refusing to choose by order"
        )


def build_operation_plan(
    source_document: SourceDocumentRef,
    upstream_versions: UpstreamVersions,
    decisions: tuple[Decision, ...],
    planned_story_part: str = PLANNED_STORY_PART,
) -> OperationPlan:
    """Aggregate Decisions into an OperationPlan.

    Calls plan_decision internally; never accepts external PlanningResults or
    arbitrary operations. Empty plan (operations == ()) is valid.
    """

    if not isinstance(source_document, SourceDocumentRef):
        raise OperationPlanContractError("source_document must be SourceDocumentRef")
    if not isinstance(upstream_versions, UpstreamVersions):
        raise OperationPlanContractError("upstream_versions must be UpstreamVersions")
    if not isinstance(decisions, tuple):
        raise OperationPlanContractError("decisions must be a tuple")
    for decision in decisions:
        if not isinstance(decision, Decision):
            raise OperationPlanContractError("decisions must contain Decision only")
    if planned_story_part != PLANNED_STORY_PART:
        raise OperationPlanContractError(
            "v0.1 only allows planned_story_part == word/document.xml"
        )

    # Identical duplicated Decisions fail before any valid plan is produced.
    seen_serialized: set[bytes] = set()
    for decision in decisions:
        blob = serialize_decision(decision)
        if blob in seen_serialized:
            raise OperationPlanAggregationError(
                "identical Decision supplied twice; this is an upstream bug"
            )
        seen_serialized.add(blob)

    _validate_homogeneity(decisions, upstream_versions)

    # planning_results are deterministically ordered by the same total key
    # used for source_decisions_hash, so that the same logical input in any
    # caller order yields byte-identical plan serialization. The trail of
    # skipped/unsupported outcomes is fully preserved — only its order is
    # canonicalized. This order is NOT document order.
    planning_results = tuple(
        result
        for _, result in sorted(
            ((decision, plan_decision(decision)) for decision in decisions),
            key=lambda pair: _decision_hash_sort_key(pair[0]),
        )
    )
    operations = tuple(
        sorted(
            (r.operation for r in planning_results if r.operation is not None),
            key=_operation_sort_key,
        )
    )
    _validate_no_duplicates_or_conflicts(operations)

    return OperationPlan(
        operation_plan_version="0.1",
        operation_vocabulary_version="0.1",
        source_document=source_document,
        planned_story_part=planned_story_part,
        upstream_versions=upstream_versions,
        source_decisions_hash=_source_decisions_hash(decisions),
        operations=operations,
        planning_results=planning_results,
    )
