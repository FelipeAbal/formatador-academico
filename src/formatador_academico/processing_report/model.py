"""Processing Report v0.1 immutable machine-readable models (decision 0034)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..classification.model import (
    ClassificationBasis,
    ClassificationProvenance,
    ClassificationReason,
    ClassificationStatus,
    ClassificationWarning,
)
from ..decision.model import (
    Actionability,
    ComplianceStatus,
    DecisionReason,
    DecisionWarning,
    EvidenceRef,
    ProfileRef,
    RuleRef,
)
from ..operation_plan.model import OperationTarget
from ..processing_session.model import (
    PROCESSING_SESSION_VERSION,
    ProcessingSessionStatus,
    SessionFindingKind,
)

PROCESSING_REPORT_VERSION = "0.1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProcessingReportError(Exception):
    """Base class for Processing Report failures."""


class ProcessingReportContractError(ProcessingReportError, ValueError):
    """Malformed input/API misuse."""


class ProcessingReportIntegrityError(ProcessingReportError):
    """Impossible cross-artifact inconsistency. Fail-fast."""


def _require_sha(name: str, value: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        raise ValueError(f"{name} must be 64 lowercase hex chars")


def _require_nonnegative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative int")


@dataclass(frozen=True)
class StoryCoverage:
    story_id: str
    total_count: int
    classified_count: int
    abstained_count: int
    not_applicable_count: int
    warning_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.story_id, str) or not self.story_id:
            raise ValueError("StoryCoverage.story_id must be non-empty")
        for name in (
            "total_count",
            "classified_count",
            "abstained_count",
            "not_applicable_count",
            "warning_count",
        ):
            _require_nonnegative_int(name, getattr(self, name))
        if (
            self.classified_count + self.abstained_count + self.not_applicable_count
            != self.total_count
        ):
            raise ValueError("StoryCoverage status counts must sum to total_count")


@dataclass(frozen=True)
class AppliedChangeItem:
    transform_ref: str
    decision_ref: str
    operation_ref: str
    profile_ref: ProfileRef
    rule_ref: RuleRef
    target: OperationTarget
    observed_before: Any
    desired_applied: Any
    input_package_sha256: str
    output_package_sha256: str
    changed_part: str
    kind: str = "applied_change"

    def __post_init__(self) -> None:
        if self.kind != "applied_change":
            raise ValueError("AppliedChangeItem.kind must be applied_change")
        for name in (
            "transform_ref",
            "decision_ref",
            "operation_ref",
            "input_package_sha256",
            "output_package_sha256",
        ):
            _require_sha(name, getattr(self, name))
        if not isinstance(self.profile_ref, ProfileRef):
            raise TypeError("profile_ref must be ProfileRef")
        if not isinstance(self.rule_ref, RuleRef):
            raise TypeError("rule_ref must be RuleRef")
        if not isinstance(self.target, OperationTarget):
            raise TypeError("target must be OperationTarget")
        if self.observed_before is None or self.desired_applied is None:
            raise ValueError("applied values must be present")
        if self.changed_part != "word/document.xml":
            raise ValueError("Processing Report v0.1 only records document.xml changes")


@dataclass(frozen=True)
class UnappliedChangeItem:
    finding_kind: SessionFindingKind
    decision_ref: str
    operation_ref: str
    profile_ref: ProfileRef
    rule_ref: RuleRef | None
    target: OperationTarget
    reason: str
    compliance: ComplianceStatus
    actionability: Actionability
    analysis_status: str
    observed: Any
    desired_value: Any
    decision_reason: DecisionReason
    kind: str = "unapplied_change"
    analysis_reason: str | None = None

    def __post_init__(self) -> None:
        if self.kind != "unapplied_change":
            raise ValueError("UnappliedChangeItem.kind must be unapplied_change")
        if not isinstance(self.finding_kind, SessionFindingKind):
            raise TypeError("finding_kind must be SessionFindingKind")
        _require_sha("decision_ref", self.decision_ref)
        _require_sha("operation_ref", self.operation_ref)
        if not isinstance(self.profile_ref, ProfileRef):
            raise TypeError("profile_ref must be ProfileRef")
        if self.rule_ref is not None and not isinstance(self.rule_ref, RuleRef):
            raise TypeError("rule_ref must be RuleRef or None")
        if not isinstance(self.target, OperationTarget):
            raise TypeError("target must be OperationTarget")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be non-empty")
        if not isinstance(self.compliance, ComplianceStatus):
            raise TypeError("compliance must be ComplianceStatus")
        if self.actionability is not Actionability.DETERMINISTIC_CHANGE:
            raise ValueError("unapplied change must be deterministic_change")
        if self.desired_value is None:
            raise ValueError("unapplied deterministic change requires desired_value")
        if not isinstance(self.analysis_status, str) or not self.analysis_status:
            raise ValueError("analysis_status must be non-empty")
        if not isinstance(self.decision_reason, DecisionReason):
            raise TypeError("decision_reason must be DecisionReason")
        if self.analysis_reason is not None and (not isinstance(self.analysis_reason, str) or not self.analysis_reason):
            raise ValueError("analysis_reason must be a non-empty str or None")


@dataclass(frozen=True)
class ReviewItem:
    decision_ref: str
    profile_ref: ProfileRef
    rule_ref: RuleRef | None
    target: OperationTarget
    compliance: ComplianceStatus
    actionability: Actionability
    reason: DecisionReason
    analysis_status: str
    observed: Any
    evidence_ref: EvidenceRef | None
    decision_warnings: tuple[DecisionWarning, ...]
    kind: str = "review_item"
    analysis_reason: str | None = None

    def __post_init__(self) -> None:
        if self.kind != "review_item":
            raise ValueError("ReviewItem.kind must be review_item")
        _require_sha("decision_ref", self.decision_ref)
        if not isinstance(self.profile_ref, ProfileRef):
            raise TypeError("profile_ref must be ProfileRef")
        if self.rule_ref is not None and not isinstance(self.rule_ref, RuleRef):
            raise TypeError("rule_ref must be RuleRef or None")
        if not isinstance(self.target, OperationTarget):
            raise TypeError("target must be OperationTarget")
        if not isinstance(self.compliance, ComplianceStatus):
            raise TypeError("compliance must be ComplianceStatus")
        if self.actionability not in {Actionability.REVIEW, Actionability.HUMAN_CHOICE}:
            raise ValueError("ReviewItem requires review or human_choice actionability")
        if not isinstance(self.reason, DecisionReason):
            raise TypeError("reason must be DecisionReason")
        if not isinstance(self.analysis_status, str) or not self.analysis_status:
            raise ValueError("analysis_status must be non-empty")
        if self.evidence_ref is not None and not isinstance(self.evidence_ref, EvidenceRef):
            raise TypeError("evidence_ref must be EvidenceRef or None")
        if not isinstance(self.decision_warnings, tuple) or not all(
            isinstance(x, DecisionWarning) for x in self.decision_warnings
        ):
            raise TypeError("decision_warnings must be tuple[DecisionWarning, ...]")
        if self.analysis_reason is not None and (not isinstance(self.analysis_reason, str) or not self.analysis_reason):
            raise ValueError("analysis_reason must be a non-empty str or None")


@dataclass(frozen=True)
class ClassificationItem:
    classification_status: ClassificationStatus
    target_type: str
    structural_path: str
    physical_hash: str
    story_id: str
    target_class: str | None
    reasons: tuple[ClassificationReason, ...]
    basis: ClassificationBasis | None
    provenance: ClassificationProvenance
    metadata: tuple[tuple[str, str | int | bool | None], ...]
    classification_warnings: tuple[ClassificationWarning, ...]
    kind: str = "classification_item"

    def __post_init__(self) -> None:
        if self.kind != "classification_item":
            raise ValueError("ClassificationItem.kind must be classification_item")
        if not isinstance(self.classification_status, ClassificationStatus):
            raise TypeError("classification_status must be ClassificationStatus")
        if self.classification_status is not ClassificationStatus.ABSTAINED and not self.classification_warnings:
            raise ValueError("ClassificationItem requires abstention or classification warning")
        if not isinstance(self.target_type, str) or not self.target_type:
            raise ValueError("target_type must be non-empty")
        if not isinstance(self.structural_path, str) or not self.structural_path:
            raise ValueError("structural_path must be non-empty")
        _require_sha("physical_hash", self.physical_hash)
        if not isinstance(self.story_id, str) or not self.story_id:
            raise ValueError("story_id must be non-empty")
        if self.target_class is not None and not isinstance(self.target_class, str):
            raise TypeError("target_class must be str or None")
        if not isinstance(self.reasons, tuple) or not all(
            isinstance(x, ClassificationReason) for x in self.reasons
        ):
            raise TypeError("reasons must be tuple[ClassificationReason, ...]")
        if self.basis is not None and not isinstance(self.basis, ClassificationBasis):
            raise TypeError("basis must be ClassificationBasis or None")
        if not isinstance(self.provenance, ClassificationProvenance):
            raise TypeError("provenance must be ClassificationProvenance")
        if not isinstance(self.metadata, tuple):
            raise TypeError("metadata must be tuple")
        if not isinstance(self.classification_warnings, tuple) or not all(
            isinstance(x, ClassificationWarning) for x in self.classification_warnings
        ):
            raise TypeError("classification_warnings must be tuple[ClassificationWarning, ...]")


@dataclass(frozen=True)
class ProcessingReportSummary:
    session_status: ProcessingSessionStatus
    applied_change_count: int
    unapplied_change_count: int
    review_item_count: int
    classification_item_count: int
    final_decision_count: int
    final_classification_count: int
    classified_count: int
    abstained_count: int
    not_applicable_count: int
    classification_warning_count: int
    story_coverage: tuple[StoryCoverage, ...]
    input_package_sha256: str
    output_package_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.session_status, ProcessingSessionStatus):
            raise TypeError("session_status must be ProcessingSessionStatus")
        for name in (
            "applied_change_count",
            "unapplied_change_count",
            "review_item_count",
            "classification_item_count",
            "final_decision_count",
            "final_classification_count",
            "classified_count",
            "abstained_count",
            "not_applicable_count",
            "classification_warning_count",
        ):
            _require_nonnegative_int(name, getattr(self, name))
        if self.classified_count + self.abstained_count + self.not_applicable_count != self.final_classification_count:
            raise ValueError("global classification status counts must sum to final_classification_count")
        if not isinstance(self.story_coverage, tuple) or not all(
            isinstance(x, StoryCoverage) for x in self.story_coverage
        ):
            raise TypeError("story_coverage must be tuple[StoryCoverage, ...]")
        if len({x.story_id for x in self.story_coverage}) != len(self.story_coverage):
            raise ValueError("story_coverage story_id values must be unique")
        if sum(x.total_count for x in self.story_coverage) != self.final_classification_count:
            raise ValueError("story_coverage totals must equal final_classification_count")
        if sum(x.classified_count for x in self.story_coverage) != self.classified_count:
            raise ValueError("story classified counts must equal global classified_count")
        if sum(x.abstained_count for x in self.story_coverage) != self.abstained_count:
            raise ValueError("story abstained counts must equal global abstained_count")
        if sum(x.not_applicable_count for x in self.story_coverage) != self.not_applicable_count:
            raise ValueError("story not_applicable counts must equal global not_applicable_count")
        if sum(x.warning_count for x in self.story_coverage) != self.classification_warning_count:
            raise ValueError("story warning counts must equal global classification_warning_count")
        _require_sha("input_package_sha256", self.input_package_sha256)
        _require_sha("output_package_sha256", self.output_package_sha256)


@dataclass(frozen=True)
class ProcessingReport:
    processing_report_version: str
    processing_session_version: str
    profile_ref: ProfileRef
    summary: ProcessingReportSummary
    applied_changes: tuple[AppliedChangeItem, ...]
    unapplied_changes: tuple[UnappliedChangeItem, ...]
    review_items: tuple[ReviewItem, ...]
    classification_items: tuple[ClassificationItem, ...]

    def __post_init__(self) -> None:
        if self.processing_report_version != PROCESSING_REPORT_VERSION:
            raise ValueError("unsupported processing_report_version")
        if self.processing_session_version != PROCESSING_SESSION_VERSION:
            raise ValueError("unsupported processing_session_version")
        if not isinstance(self.profile_ref, ProfileRef):
            raise TypeError("profile_ref must be ProfileRef")
        if not isinstance(self.summary, ProcessingReportSummary):
            raise TypeError("summary must be ProcessingReportSummary")
        typed = (
            ("applied_changes", AppliedChangeItem),
            ("unapplied_changes", UnappliedChangeItem),
            ("review_items", ReviewItem),
            ("classification_items", ClassificationItem),
        )
        for name, cls in typed:
            value = getattr(self, name)
            if not isinstance(value, tuple) or not all(isinstance(x, cls) for x in value):
                raise TypeError(f"{name} must be tuple[{cls.__name__}, ...]")
        if self.summary.applied_change_count != len(self.applied_changes):
            raise ValueError("summary applied_change_count mismatch")
        if self.summary.unapplied_change_count != len(self.unapplied_changes):
            raise ValueError("summary unapplied_change_count mismatch")
        if self.summary.review_item_count != len(self.review_items):
            raise ValueError("summary review_item_count mismatch")
        if self.summary.classification_item_count != len(self.classification_items):
            raise ValueError("summary classification_item_count mismatch")
        for item in self.applied_changes:
            if item.profile_ref != self.profile_ref:
                raise ValueError("applied item profile_ref mismatch")
        for item in self.unapplied_changes:
            if item.profile_ref != self.profile_ref:
                raise ValueError("unapplied item profile_ref mismatch")
        for item in self.review_items:
            if item.profile_ref != self.profile_ref:
                raise ValueError("review item profile_ref mismatch")
