"""Processing Session v0.1 public immutable models (decision 0032)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from ..classification.model import ClassificationResult
from ..decision.model import Actionability, Decision, FormattingRule, ProfileRef, RuleMode
from ..operation_plan import decision_ref as canonical_decision_ref
from ..operation_plan.model import OperationTarget
from ..patcher.model import PatchReason
from ..safety_gate.model import GateReason
from ..transform_log.model import TransformRecord

PROCESSING_SESSION_VERSION = "0.1"
DEFAULT_MAX_APPLIED_OPERATIONS = 10000

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_CLASSES = frozenset({"body", "heading"})
_SUPPORTED_BINDINGS = frozenset({
    ("run", "P1", "bold"),
    ("run", "P2", "font_size"),
    ("paragraph", "P4", "alignment"),
    ("paragraph", "P3", "spacing.line"),
})
_ALLOWED_PATCH_FINDING_REASONS = frozenset(
    {
        PatchReason.NONCANONICAL_RUN_PROPERTIES.value,
        PatchReason.DUPLICATE_TARGET_PROPERTY.value,
        PatchReason.UNREPRESENTABLE_VALUE.value,
    }
)
_GATE_REASON_VALUES = frozenset(reason.value for reason in GateReason)


class ProcessingSessionError(Exception):
    """Base class for Processing Session failures."""


class ProcessingSessionContractError(ProcessingSessionError, ValueError):
    """Malformed input/profile/API misuse."""


class ProcessingSessionIntegrityError(ProcessingSessionError):
    """Impossible cross-artifact/cycle/lineage contradiction."""


class ProcessingSessionStatus(str, Enum):
    """Technical automatic-processing state; never a claim of full conformity."""

    QUIESCENT = "quiescent"
    QUIESCENT_WITH_UNAPPLIED = "quiescent_with_unapplied"
    OPERATION_LIMIT_REACHED = "operation_limit_reached"


class SessionFindingKind(str, Enum):
    GATE_BLOCKED = "gate_blocked"
    PATCH_REJECTED = "patch_rejected"
    OPERATION_LIMIT = "operation_limit"


def _validate_rule_value(property_slot: str, value: object) -> None:
    if property_slot == "bold":
        if type(value) is not bool:
            raise ProcessingSessionContractError("bold rule values must be exact bool")
        return
    if property_slot == "font_size":
        if type(value) is not Decimal:
            raise ProcessingSessionContractError(
                "font_size rule values must be Decimal points"
            )
        return
    if property_slot == "alignment":
        if type(value) is not str or value not in {"left", "center", "right", "both"}:
            raise ProcessingSessionContractError(
                "alignment rule values must be canonical left/center/right/both tokens"
            )
        return
    if property_slot == "spacing.line":
        if type(value).__name__ != "LineSpacingValue":
            raise ProcessingSessionContractError("spacing.line rule values must be LineSpacingValue")
        if value.rule != "auto" or value.unit != "multiple" or value.value is None:
            raise ProcessingSessionContractError("spacing.line rule values must be auto multiples")
        if not isinstance(value.value, Decimal) or value.value <= 0:
            raise ProcessingSessionContractError("spacing.line multiple must be a positive Decimal")
        return
    raise ProcessingSessionContractError("unsupported Processing Session property slot")


def _validate_bound_rule(rule: FormattingRule) -> None:
    if not isinstance(rule.rule_id, str) or not rule.rule_id:
        raise ProcessingSessionContractError("FormattingRule.rule_id must be non-empty")
    if rule.mode is RuleMode.CONTAINMENT:
        return
    if rule.mode is RuleMode.EXACT:
        _validate_rule_value(rule.property_slot, rule.expected)
        return
    if rule.mode is RuleMode.SET:
        for value in rule.allowed:
            _validate_rule_value(rule.property_slot, value)
        if rule.preferred is not None:
            _validate_rule_value(rule.property_slot, rule.preferred)
        return
    raise ProcessingSessionContractError("unsupported FormattingRule.mode")


@dataclass(frozen=True)
class RuleBinding:
    """Minimal v0.1 mapping from a classified target class to one frozen rule."""

    target_class: str
    target_type: str
    rule: FormattingRule

    def __post_init__(self) -> None:
        if self.target_class not in _SUPPORTED_CLASSES:
            raise ProcessingSessionContractError(
                "RuleBinding.target_class must be one of body/heading in v0.1"
            )
        if self.target_type not in {"run", "paragraph"}:
            raise ProcessingSessionContractError(
                "RuleBinding target_type must be run or paragraph"
            )
        if not isinstance(self.rule, FormattingRule):
            raise ProcessingSessionContractError("RuleBinding.rule must be FormattingRule")
        key = (self.target_type, self.rule.aspect_id, self.rule.property_slot)
        if key not in _SUPPORTED_BINDINGS:
            raise ProcessingSessionContractError(
                "RuleBinding operation is outside Processing Session v0.1 slice"
            )
        _validate_bound_rule(self.rule)

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.target_class,
            self.target_type,
            self.rule.aspect_id,
            self.rule.property_slot,
        )

    @property
    def canonical_sort_key(self) -> tuple[str, ...]:
        return (
            self.target_class,
            self.target_type,
            self.rule.aspect_id,
            self.rule.property_slot,
            self.rule.rule_id,
            self.rule.path or "",
        )


@dataclass(frozen=True)
class ProcessingProfile:
    """Minimal orchestration profile aggregate; not the future UI profile schema."""

    profile_ref: ProfileRef
    bindings: tuple[RuleBinding, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profile_ref, ProfileRef):
            raise ProcessingSessionContractError("ProcessingProfile.profile_ref must be ProfileRef")
        if not isinstance(self.profile_ref.profile_id, str) or not self.profile_ref.profile_id:
            raise ProcessingSessionContractError("profile_id must be non-empty")
        if not isinstance(self.profile_ref.profile_version, str) or not self.profile_ref.profile_version:
            raise ProcessingSessionContractError("profile_version must be non-empty")
        if not isinstance(self.bindings, tuple):
            raise ProcessingSessionContractError("ProcessingProfile.bindings must be a tuple")
        if not self.bindings:
            raise ProcessingSessionContractError("ProcessingProfile.bindings must be non-empty")
        seen: set[tuple[str, str, str, str]] = set()
        for binding in self.bindings:
            if not isinstance(binding, RuleBinding):
                raise ProcessingSessionContractError(
                    "ProcessingProfile.bindings must contain RuleBinding only"
                )
            if binding.identity in seen:
                raise ProcessingSessionContractError(
                    f"duplicate/conflicting RuleBinding identity: {binding.identity}"
                )
            seen.add(binding.identity)

    @property
    def canonical_bindings(self) -> tuple[RuleBinding, ...]:
        return tuple(sorted(self.bindings, key=lambda b: b.canonical_sort_key))


@dataclass(frozen=True)
class SessionFinding:
    """Final/current-snapshot execution finding; always bound to one operation."""

    kind: SessionFindingKind
    decision_ref: str
    operation_ref: str
    target: OperationTarget
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SessionFindingKind):
            raise TypeError("SessionFinding.kind must be SessionFindingKind")
        for name in ("decision_ref", "operation_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256_RE.match(value):
                raise ValueError(f"SessionFinding.{name} must be lowercase sha256")
        if not isinstance(self.target, OperationTarget):
            raise TypeError("SessionFinding.target must be OperationTarget")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("SessionFinding.reason must be non-empty")

        if self.kind is SessionFindingKind.GATE_BLOCKED:
            if self.reason not in _GATE_REASON_VALUES:
                raise ValueError("gate_blocked finding requires a GateReason value")
        elif self.kind is SessionFindingKind.PATCH_REJECTED:
            if self.reason not in _ALLOWED_PATCH_FINDING_REASONS:
                raise ValueError(
                    "patch_rejected finding requires an allowed physical Patcher rejection reason"
                )
        elif self.kind is SessionFindingKind.OPERATION_LIMIT:
            if self.reason != ProcessingSessionStatus.OPERATION_LIMIT_REACHED.value:
                raise ValueError(
                    "operation_limit finding reason must equal operation_limit_reached"
                )


def _target_matches_decision(target: OperationTarget, decision: Decision) -> bool:
    dt = decision.target
    return (
        target.target_type == dt.target_type
        and target.structural_path == dt.structural_path
        and target.physical_hash == dt.physical_hash
        and target.target_class == dt.target_class
        and target.aspect_id == dt.aspect_id
        and target.property_slot == dt.property_slot
    )


@dataclass(frozen=True)
class ProcessingSessionResult:
    processing_session_version: str
    status: ProcessingSessionStatus
    profile_ref: ProfileRef
    input_package_sha256: str
    output_package_sha256: str
    output_package_bytes: bytes
    transforms: tuple[TransformRecord, ...]
    final_classifications: tuple[ClassificationResult, ...]
    final_decisions: tuple[Decision, ...]
    findings: tuple[SessionFinding, ...]

    def __post_init__(self) -> None:
        if self.processing_session_version != PROCESSING_SESSION_VERSION:
            raise ValueError("unsupported processing_session_version")
        if not isinstance(self.status, ProcessingSessionStatus):
            raise TypeError("status must be ProcessingSessionStatus")
        if not isinstance(self.profile_ref, ProfileRef):
            raise TypeError("profile_ref must be ProfileRef")
        for name in ("input_package_sha256", "output_package_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256_RE.match(value):
                raise ValueError(f"{name} must be lowercase sha256")
        if not isinstance(self.output_package_bytes, bytes) or not self.output_package_bytes:
            raise ValueError("output_package_bytes must be non-empty bytes")
        actual = hashlib.sha256(self.output_package_bytes).hexdigest()
        if actual != self.output_package_sha256:
            raise ValueError("output_package_sha256 must match output_package_bytes")
        if not isinstance(self.transforms, tuple) or not all(
            isinstance(x, TransformRecord) for x in self.transforms
        ):
            raise TypeError("transforms must be tuple[TransformRecord, ...]")
        if not isinstance(self.final_classifications, tuple) or not all(
            isinstance(x, ClassificationResult) for x in self.final_classifications
        ):
            raise TypeError("final_classifications must be tuple[ClassificationResult, ...]")
        if not isinstance(self.final_decisions, tuple) or not all(
            isinstance(x, Decision) for x in self.final_decisions
        ):
            raise TypeError("final_decisions must be tuple[Decision, ...]")
        if not isinstance(self.findings, tuple) or not all(
            isinstance(x, SessionFinding) for x in self.findings
        ):
            raise TypeError("findings must be tuple[SessionFinding, ...]")

        for transform in self.transforms:
            if transform.profile_ref != self.profile_ref:
                raise ValueError("all TransformRecords must use the session profile_ref")
        for decision in self.final_decisions:
            if decision.profile_ref != self.profile_ref:
                raise ValueError("all final Decisions must use the session profile_ref")

        final_by_ref = {canonical_decision_ref(d): d for d in self.final_decisions}
        if len(final_by_ref) != len(self.final_decisions):
            raise ValueError("final_decisions must have unique canonical decision refs")
        for finding in self.findings:
            decision = final_by_ref.get(finding.decision_ref)
            if decision is None:
                raise ValueError("every finding must bind to a final Decision")
            if decision.actionability is not Actionability.DETERMINISTIC_CHANGE:
                raise ValueError("execution finding must bind to deterministic_change Decision")
            if not _target_matches_decision(finding.target, decision):
                raise ValueError("finding target must match its final Decision target")

        if not self.transforms:
            if self.input_package_sha256 != self.output_package_sha256:
                raise ValueError("zero-transform session must preserve package SHA")
        else:
            if self.transforms[0].input_package_sha256 != self.input_package_sha256:
                raise ValueError("first TransformRecord must start from session input SHA")
            if self.transforms[-1].output_package_sha256 != self.output_package_sha256:
                raise ValueError("last TransformRecord must end at session output SHA")
            for left, right in zip(self.transforms, self.transforms[1:]):
                if left.output_package_sha256 != right.input_package_sha256:
                    raise ValueError("TransformRecord chain is not contiguous")

        deterministic_final = tuple(
            d for d in self.final_decisions
            if d.actionability is Actionability.DETERMINISTIC_CHANGE
        )
        if self.status is ProcessingSessionStatus.QUIESCENT:
            if self.findings or deterministic_final:
                raise ValueError(
                    "quiescent session cannot carry unresolved execution findings/change Decisions"
                )
        elif self.status is ProcessingSessionStatus.QUIESCENT_WITH_UNAPPLIED:
            if not deterministic_final:
                raise ValueError(
                    "quiescent_with_unapplied requires final deterministic_change Decisions"
                )
            if not any(
                f.kind in {SessionFindingKind.GATE_BLOCKED, SessionFindingKind.PATCH_REJECTED}
                for f in self.findings
            ):
                raise ValueError(
                    "quiescent_with_unapplied requires gate/patch unresolved findings"
                )
        elif self.status is ProcessingSessionStatus.OPERATION_LIMIT_REACHED:
            if not deterministic_final:
                raise ValueError(
                    "operation_limit_reached requires a remaining deterministic_change Decision"
                )
            if not any(f.kind is SessionFindingKind.OPERATION_LIMIT for f in self.findings):
                raise ValueError("operation_limit_reached requires operation_limit finding")
