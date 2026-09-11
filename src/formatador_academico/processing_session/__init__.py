"""Processing Session / Orchestration v0.1 public API."""

from .engine import process_document
from .model import (
    DEFAULT_MAX_APPLIED_OPERATIONS,
    PROCESSING_SESSION_VERSION,
    ProcessingProfile,
    ProcessingSessionContractError,
    ProcessingSessionUnsupportedError,
    ProcessingSessionError,
    ProcessingSessionIntegrityError,
    ProcessingSessionResult,
    ProcessingSessionStatus,
    RuleBinding,
    SessionFinding,
    SessionFindingKind,
)

__all__ = [
    "DEFAULT_MAX_APPLIED_OPERATIONS",
    "PROCESSING_SESSION_VERSION",
    "ProcessingProfile",
    "ProcessingSessionContractError",
    "ProcessingSessionUnsupportedError",
    "ProcessingSessionError",
    "ProcessingSessionIntegrityError",
    "ProcessingSessionResult",
    "ProcessingSessionStatus",
    "RuleBinding",
    "SessionFinding",
    "SessionFindingKind",
    "process_document",
]
