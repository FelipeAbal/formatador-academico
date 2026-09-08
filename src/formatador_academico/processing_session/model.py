"""Processing Session v0.1 public immutable models (decision 0032)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

from ..classification.model import ClassificationResult
from ..decision.model import Decision, FormattingRule, ProfileRef
from ..operation_plan.model import OperationTarget
from ..transform_log.model import TransformRecord

PROCESSING_SESSION_VERSION = "0.1"
DEFAULT_MAX_APPLIED_OPERATIONS = 10000

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_CLASSES = frozenset({"body", "heading"})
_SUPPORTED_BINDINGS = frozenset({("run", "P1", "bold"), ("run", "P2", "font_size")})


class ProcessingSessionError(Exception):
    """Base class for Processing Session failures."""


class ProcessingSessionContractError(ProcessingSessionError, ValueError):
    """Malformed input/profile/API misuse."""


class ProcessingSessionIntegrityError(ProcessingSessionError):
    """Impossible cross-artifact/cycle/lineage contradiction."""


class ProcessingSessionStatus(str, Enum):
    QUIESCENT = "quiescent"
    QUIESCENT_WITH_UNAPPLIED = "quiescent_with_unapplied"
    OPERATION_LIMIT_REACHED = "operation_limit_reached"


class SessionFindingKind(str, Enum):
    GATE_BLOCKED = "gate_blocked"
    PATCH_REJECTED = "patch_rejected"
    OPERATION_LIMIT = "operation_limit"


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
        if self.target_type != "run":
            raise ProcessingSessionContractError("RuleBinding v0.1 only supports target_type='run'")
        if not isinstance(self.rule, FormattingRule):
            raise ProcessingSessionContractError("RuleBinding.rule must be FormattingRule")
        key = (self.target_type, self.rule.aspect_id, self.rule.property_slot)
        if key not in _SUPPORTED_BINDINGS:
            raise ProcessingSessionContractError(
                "RuleBinding operation is outside Processing Session v0.1 slice"
            )

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
    kind: SessionFindingKind
    decision_ref: str
    operation_ref: str | None
    target: OperationTarget
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SessionFindingKind):
            raise TypeError("SessionFinding.kind must be SessionFindingKind")
        if not isinstance(self.decision_ref, str) or not _SHA256_RE.match(self.decision_ref):
            raise ValueError("SessionFinding.decision_ref must be lowercase sha256")
        if self.operation_ref is not None and (
            not isinstance(self.operation_ref, str) or not _SHA256_RE.match(self.operation_ref)
        ):
            raise ValueError("SessionFinding.operation_ref must be lowercase sha256 or None")
        if not isinstance(self.target, OperationTarget):
            raise TypeError("SessionFinding.target must be OperationTarget")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("SessionFinding.reason must be non-empty")


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
