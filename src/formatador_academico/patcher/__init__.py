"""Patcher v0.1 — first executable slice (decision 0028).

    GateClearedOperation + package snapshot bytes -> PatchResult

Executable slice: P1/run/bold and P2/run/font_size, one operation per call.
The patcher is an executor only: OperationPlan proposes, SafetyGate vetoes,
the Patcher applies the exact cleared mutation on the exact gated snapshot
and proves (allowed-delta + semantic postcondition) that nothing else moved.
"""

from .applicator import apply_cleared_operation
from .model import (
    DOCUMENT_PART,
    PATCHER_VERSION,
    PatchReason,
    PatchResult,
    PatchStatus,
    PatcherContractError,
    PatcherError,
    PatcherIntegrityError,
)
from .xml_patch import MAX_HALF_POINTS

__all__ = [
    "DOCUMENT_PART",
    "MAX_HALF_POINTS",
    "PATCHER_VERSION",
    "PatchReason",
    "PatchResult",
    "PatchStatus",
    "PatcherContractError",
    "PatcherError",
    "PatcherIntegrityError",
    "apply_cleared_operation",
]
