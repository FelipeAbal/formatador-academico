"""SafetyGate v0.1 public immutable models.

Contract: docs/decisions/0026-safety-gate-v01-contract.md.

SafetyGate is a FINAL VETO layer, never a new authorization: `cleared` means
only that no SafetyGate veto fired against the current observed state. All
models are frozen dataclasses with tuples; no timestamps, no randomness, no
IO, no LLM, no heuristics/confidence/risk scores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..operation_plan.model import PlannedOperation

SAFETY_GATE_VERSION = "0.1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SafetyGateError(Exception):
    """Base class for SafetyGate failures."""


class SafetyGateContractError(SafetyGateError, ValueError):
    """Malformed/incompatible artifact or API misuse. Fail-fast."""


class SafetyGateIntegrityError(SafetyGateError):
    """Provenance/integrity/binding failure. Fail-fast. Never a veto."""


class GateStatus(str, Enum):
    """`cleared` means ONLY: no SafetyGate veto fired on the observed state.

    It is not `safe`, `authorized` or `approved` — SafetyGate never grants
    new normative authorization.
    """

    CLEARED = "cleared"
    BLOCKED = "blocked"


class ContextStatus(str, Enum):
    COMPATIBLE = "compatible"
    BLOCKED = "blocked"


class GateReason(str, Enum):
    """Closed v0.1 reason vocabulary, frozen under SAFETY_GATE_VERSION.

    Any semantic change to a reason requires a SafetyGate version bump.
    There is intentionally no `evaluation_error`: unexpected Analysis
    exceptions are fail-fast programming/contract failures.
    """

    # Global (context) vetoes
    SOURCE_DOCUMENT_CHANGED = "source_document_changed"
    PARSER_VERSION_MISMATCH = "parser_version_mismatch"
    ANALYSIS_VERSION_MISMATCH = "analysis_version_mismatch"
    CLASSIFICATION_VERSION_MISMATCH = "classification_version_mismatch"
    PROFILE_CONTEXT_CHANGED = "profile_context_changed"
    # Local (per-operation) vetoes
    TARGET_NOT_FOUND = "target_not_found"
    TARGET_NOT_UNIQUE = "target_not_unique"
    TARGET_TYPE_MISMATCH = "target_type_mismatch"
    PHYSICAL_HASH_MISMATCH = "physical_hash_mismatch"
    CURRENT_VALUE_UNAVAILABLE = "current_value_unavailable"
    PRECONDITION_MISMATCH = "precondition_mismatch"


GLOBAL_REASONS = frozenset(
    {
        GateReason.SOURCE_DOCUMENT_CHANGED,
        GateReason.PARSER_VERSION_MISMATCH,
        GateReason.ANALYSIS_VERSION_MISMATCH,
        GateReason.CLASSIFICATION_VERSION_MISMATCH,
        GateReason.PROFILE_CONTEXT_CHANGED,
    }
)

LOCAL_REASONS = frozenset(
    {
        GateReason.TARGET_NOT_FOUND,
        GateReason.TARGET_NOT_UNIQUE,
        GateReason.TARGET_TYPE_MISMATCH,
        GateReason.PHYSICAL_HASH_MISMATCH,
        GateReason.CURRENT_VALUE_UNAVAILABLE,
        GateReason.PRECONDITION_MISMATCH,
    }
)


@dataclass(frozen=True)
class GateEvidence:
    """Minimal factual evidence for the check that produced the result.

    Fields hold typed semantic values (hashes, bool, str, LengthValue,
    LineSpacingValue) or None when not applicable:

    - expected: the planned/expected value of the failed check;
    - actual: the currently observed counterpart of the failed check;
    - current_observed: the re-observed current semantic value (recorded
      at least for cleared results, where it equals the precondition).

    No dicts, no mutable structures; never repeats the whole plan.
    """

    expected: Any = None
    actual: Any = None
    current_observed: Any = None


@dataclass(frozen=True)
class GateResult:
    """Per-operation gate verdict. Does NOT embed the PlannedOperation."""

    operation_ref: str
    status: GateStatus
    reasons: tuple[GateReason, ...]
    evidence: GateEvidence | None

    def __post_init__(self) -> None:
        if not isinstance(self.operation_ref, str) or not _SHA256_RE.match(self.operation_ref):
            raise ValueError("GateResult.operation_ref must be 64 lowercase hex chars")
        if not isinstance(self.status, GateStatus):
            raise TypeError("GateResult.status must be GateStatus")
        if not isinstance(self.reasons, tuple):
            raise TypeError("GateResult.reasons must be a tuple")
        for reason in self.reasons:
            if not isinstance(reason, GateReason):
                raise TypeError("GateResult.reasons must contain GateReason only")
        if self.status is GateStatus.CLEARED and self.reasons:
            raise ValueError("cleared GateResult must have empty reasons")
        if self.status is GateStatus.BLOCKED and len(self.reasons) != 1:
            raise ValueError("blocked GateResult carries exactly 1 reason in v0.1")
        if self.evidence is not None and not isinstance(self.evidence, GateEvidence):
            raise TypeError("GateResult.evidence must be GateEvidence or None")


# Internal emission proof: GateClearedOperation instances can only be created
# inside the gate flow (see gate.py). There is intentionally no public
# constructor helper such as `GateClearedOperation.from_operation(...)`:
# bypass must be non-accidental (Python cannot offer absolute type safety).
_EMISSION_PROOF = object()


@dataclass(frozen=True)
class GateClearedOperation:
    """Typed execution-boundary token for the future patcher.

    This is NOT a new normative authorization; it only proves that no veto
    condition of SafetyGate v0.1 failed on that snapshot. The embedded
    PlannedOperation is field/byte-equivalent to the input operation.

    Future patchers MUST accept GateClearedOperation, never a raw
    PlannedOperation, and MUST operate on the same snapshot identified by
    `current_package_sha256` (TOCTOU contract, decision 0026).
    """

    operation: PlannedOperation
    operation_ref: str
    operation_plan_ref: str
    current_package_sha256: str
    _proof: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._proof is not _EMISSION_PROOF:
            raise SafetyGateContractError(
                "GateClearedOperation can only be emitted by the SafetyGate flow; "
                "there is no public promotion of a PlannedOperation"
            )
        if not isinstance(self.operation, PlannedOperation):
            raise TypeError("GateClearedOperation.operation must be PlannedOperation")
        for name in ("operation_ref", "operation_plan_ref", "current_package_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256_RE.match(value):
                raise ValueError(f"GateClearedOperation.{name} must be 64 lowercase hex chars")


@dataclass(frozen=True)
class SafetyGateReport:
    """Gate output for one OperationPlan against one observed snapshot.

    `results` follow exactly the canonical order of `plan.operations`.
    `cleared_operations` corresponds exactly to the cleared GateResults;
    when the context is blocked it must be empty.
    """

    safety_gate_version: str
    operation_plan_ref: str
    current_package_sha256: str
    context_status: ContextStatus
    context_reasons: tuple[GateReason, ...]
    results: tuple[GateResult, ...]
    cleared_operations: tuple[GateClearedOperation, ...]

    def __post_init__(self) -> None:
        if self.safety_gate_version != SAFETY_GATE_VERSION:
            raise ValueError("unsupported safety_gate_version")
        for name in ("operation_plan_ref", "current_package_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256_RE.match(value):
                raise ValueError(f"SafetyGateReport.{name} must be 64 lowercase hex chars")
        if not isinstance(self.context_status, ContextStatus):
            raise TypeError("context_status must be ContextStatus")
        if not isinstance(self.context_reasons, tuple):
            raise TypeError("context_reasons must be a tuple")
        for reason in self.context_reasons:
            if not isinstance(reason, GateReason) or reason not in GLOBAL_REASONS:
                raise ValueError("context_reasons must be global GateReason values")
        if self.context_status is ContextStatus.COMPATIBLE and self.context_reasons:
            raise ValueError("compatible context requires empty context_reasons")
        if self.context_status is ContextStatus.BLOCKED and not self.context_reasons:
            raise ValueError("blocked context requires >= 1 global reason")
        if not isinstance(self.results, tuple) or not all(
            isinstance(r, GateResult) for r in self.results
        ):
            raise TypeError("results must be a tuple of GateResult")
        if not isinstance(self.cleared_operations, tuple) or not all(
            isinstance(o, GateClearedOperation) for o in self.cleared_operations
        ):
            raise TypeError("cleared_operations must be a tuple of GateClearedOperation")
        # Consistency: cleared_operations correspond exactly to cleared results.
        cleared_refs = tuple(r.operation_ref for r in self.results if r.status is GateStatus.CLEARED)
        emitted_refs = tuple(o.operation_ref for o in self.cleared_operations)
        if emitted_refs != cleared_refs:
            raise ValueError(
                "cleared_operations must correspond exactly (and in order) to cleared results"
            )
        for cleared in self.cleared_operations:
            if cleared.operation_plan_ref != self.operation_plan_ref:
                raise ValueError("cleared operation plan ref disagrees with the report")
            if cleared.current_package_sha256 != self.current_package_sha256:
                raise ValueError("cleared operation snapshot disagrees with the report")
        if self.context_status is ContextStatus.BLOCKED and self.cleared_operations:
            raise ValueError("no GateClearedOperation may exist when context is blocked")
