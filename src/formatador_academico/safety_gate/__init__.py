"""SafetyGate v0.1 — first vertical slice (OperationPlan -> SafetyGateReport).

Contract: docs/decisions/0026-safety-gate-v01-contract.md.

SafetyGate is the FINAL VETO layer: `cleared` means only that no veto fired
against the current observed state — never a new normative authorization.

Boundary for the future patcher: patchers MUST accept GateClearedOperation,
never a raw PlannedOperation, and MUST operate on the same snapshot
identified by `current_package_sha256` (TOCTOU contract).

No XML patch, no DOCX mutation, no TransformLog in this slice.
"""

from .gate import evaluate_operation_plan, gate_operation
from .model import (
    GLOBAL_REASONS,
    LOCAL_REASONS,
    SAFETY_GATE_VERSION,
    ContextStatus,
    GateClearedOperation,
    GateEvidence,
    GateReason,
    GateResult,
    GateStatus,
    SafetyGateContractError,
    SafetyGateError,
    SafetyGateIntegrityError,
    SafetyGateReport,
)
from .serialization import serialize_gate_result, serialize_safety_gate_report

__all__ = [
    "GLOBAL_REASONS",
    "LOCAL_REASONS",
    "SAFETY_GATE_VERSION",
    "ContextStatus",
    "GateClearedOperation",
    "GateEvidence",
    "GateReason",
    "GateResult",
    "GateStatus",
    "SafetyGateContractError",
    "SafetyGateError",
    "SafetyGateIntegrityError",
    "SafetyGateReport",
    "evaluate_operation_plan",
    "gate_operation",
    "serialize_gate_result",
    "serialize_safety_gate_report",
]
