"""OperationPlan v0.1 public immutable models.

Contract: docs/decisions/0024-operation-plan-v01-contract.md.

All models are frozen dataclasses; tuples instead of mutable lists; no
timestamps, no randomness, no IO. Values remain semantic (never OOXML):
bold -> bool, font_size -> LengthValue(pt), alignment -> canonical token,
spacing.line -> decision.model.LineSpacingValue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from ..decision.model import DecisionKey, LineSpacingValue

OPERATION_PLAN_VERSION = "0.1"
OPERATION_VOCABULARY_VERSION = "0.1"

# Slice v0.1: DecisionTarget does not carry story_id/part and only the main
# story is executable, so the envelope declares this single part explicitly.
PLANNED_STORY_PART = "word/document.xml"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class OperationKind(str, Enum):
    """Only SET_PROPERTY exists in v0.1.

    MOVE_BLOCK / INSERT_BLOCK / MERGE_BLOCKS / DELETE / REWRITE remain
    reserved as future expansion (decision 0002) and are intentionally NOT
    implemented as empty classes.
    """

    SET_PROPERTY = "set_property"


class PlanningStatus(str, Enum):
    PLANNED = "planned"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class LengthValue:
    """Semantic length with explicit unit. v0.1 accepts only `pt`."""

    value: Decimal
    unit: str = "pt"

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError("LengthValue.value must be Decimal")
        if self.unit != "pt":
            raise ValueError("LengthValue v0.1 only accepts unit 'pt'")


@dataclass(frozen=True)
class OperationTarget:
    """Faithful copy of DecisionTarget. Never recalculated, never reinterpreted."""

    target_type: str
    structural_path: str
    physical_hash: str
    target_class: str
    aspect_id: str
    property_slot: str

    def __post_init__(self) -> None:
        if not self.structural_path:
            raise ValueError("OperationTarget.structural_path must be non-empty")
        if not isinstance(self.physical_hash, str) or not self.physical_hash:
            raise ValueError("OperationTarget.physical_hash must be a non-empty string")


@dataclass(frozen=True)
class PlannedOperation:
    """One intention = at most one property mutation (compare-and-set)."""

    kind: OperationKind
    key: DecisionKey
    target: OperationTarget
    precondition_observed: Any
    desired_value: Any
    decision_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, OperationKind):
            raise TypeError("PlannedOperation.kind must be OperationKind")
        if not isinstance(self.key, DecisionKey):
            raise TypeError("PlannedOperation.key must be DecisionKey")
        if not isinstance(self.target, OperationTarget):
            raise TypeError("PlannedOperation.target must be OperationTarget")
        if self.precondition_observed is None:
            raise ValueError("precondition_observed is mandatory for SET_PROPERTY")
        if self.desired_value is None:
            raise ValueError("desired_value is mandatory for SET_PROPERTY")
        if self.precondition_observed == self.desired_value:
            raise ValueError("precondition_observed must differ from desired_value")
        if not _SHA256_RE.match(self.decision_ref):
            raise ValueError("decision_ref must be a lowercase sha256 hex digest")
        # Binding invariant: key and target address the same property.
        if self.key.target_type != self.target.target_type:
            raise ValueError("operation key/target target_type mismatch")
        if self.key.aspect_id != self.target.aspect_id:
            raise ValueError("operation key/target aspect_id mismatch")
        if self.key.property_slot != self.target.property_slot:
            raise ValueError("operation key/target property_slot mismatch")


@dataclass(frozen=True)
class PlanningResult:
    """Never None for a valid Decision.

    Invariant: status == planned IFF operation is not None.
    """

    decision_ref: str
    status: PlanningStatus
    operation: PlannedOperation | None
    decision_actionability: str
    decision_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, PlanningStatus):
            raise TypeError("PlanningResult.status must be PlanningStatus")
        planned = self.status is PlanningStatus.PLANNED
        if planned != (self.operation is not None):
            raise ValueError("status == planned iff operation is not None")
        if not _SHA256_RE.match(self.decision_ref):
            raise ValueError("decision_ref must be a lowercase sha256 hex digest")


@dataclass(frozen=True)
class SourceDocumentRef:
    """Anchor to the source document. Values come from the PhysicalIR that
    originated the Decisions; never recomputed by the planner."""

    package_sha256: str
    parser_version: str

    def __post_init__(self) -> None:
        if not _SHA256_RE.match(self.package_sha256):
            raise ValueError("package_sha256 must be 64 lowercase hex chars")
        if not isinstance(self.parser_version, str) or not self.parser_version:
            raise ValueError("parser_version must be a non-empty string")


@dataclass(frozen=True)
class UpstreamVersions:
    """Recorded once per plan. Parser version lives in SourceDocumentRef."""

    analysis_formatting_version: str
    classification_version: str
    decision_version: str
    decision_vocabulary_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "analysis_formatting_version",
            "classification_version",
            "decision_version",
            "decision_vocabulary_version",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"UpstreamVersions.{field_name} must be a non-empty string")


@dataclass(frozen=True)
class OperationPlan:
    """Executable plan envelope.

    `operations` is the executable plan (mutation budget).
    `planning_results` is the planning trail, preserving skipped/unsupported
    outcomes for reporting.
    """

    operation_plan_version: str
    operation_vocabulary_version: str
    source_document: SourceDocumentRef
    planned_story_part: str
    upstream_versions: UpstreamVersions
    source_decisions_hash: str
    operations: tuple[PlannedOperation, ...]
    planning_results: tuple[PlanningResult, ...]

    def __post_init__(self) -> None:
        if self.operation_plan_version != OPERATION_PLAN_VERSION:
            raise ValueError("unsupported operation_plan_version")
        if self.operation_vocabulary_version != OPERATION_VOCABULARY_VERSION:
            raise ValueError("unsupported operation_vocabulary_version")
        if not isinstance(self.source_document, SourceDocumentRef):
            raise TypeError("source_document must be SourceDocumentRef")
        if self.planned_story_part != PLANNED_STORY_PART:
            raise ValueError("v0.1 only allows planned_story_part == word/document.xml")
        if not isinstance(self.upstream_versions, UpstreamVersions):
            raise TypeError("upstream_versions must be UpstreamVersions")
        if not _SHA256_RE.match(self.source_decisions_hash):
            raise ValueError("source_decisions_hash must be a lowercase sha256 hex digest")
        if not isinstance(self.operations, tuple):
            raise TypeError("operations must be a tuple")
        if not isinstance(self.planning_results, tuple):
            raise TypeError("planning_results must be a tuple")
        for operation in self.operations:
            if not isinstance(operation, PlannedOperation):
                raise TypeError("operations must contain PlannedOperation only")
        for result in self.planning_results:
            if not isinstance(result, PlanningResult):
                raise TypeError("planning_results must contain PlanningResult only")
        # operations must be exactly the planned operations of the trail.
        trail_operations = tuple(
            result.operation for result in self.planning_results if result.operation is not None
        )
        if tuple(sorted(trail_operations, key=_operation_sort_key)) != tuple(
            sorted(self.operations, key=_operation_sort_key)
        ):
            raise ValueError("operations must equal the planned operations of planning_results")


def _operation_sort_key(operation: PlannedOperation) -> tuple[str, ...]:
    """Total deterministic order for serialization only.

    This is NOT document order nor future application order (decision 0024).
    """
    return (
        PLANNED_STORY_PART,
        operation.target.structural_path,
        operation.target.physical_hash,
        operation.target.aspect_id,
        operation.target.property_slot,
    )
