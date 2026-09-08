"""TransformLog v0.1 immutable forensic model (decision 0030)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..decision.model import ProfileRef, RuleRef
from ..operation_plan.model import OperationTarget
from ..patcher.model import PATCHER_VERSION

TRANSFORM_LOG_VERSION = "0.1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TransformLogError(Exception):
    """Base class for TransformLog failures."""


class TransformLogContractError(TransformLogError, ValueError):
    """Malformed/incompatible input artifact or API misuse."""


class TransformLogIntegrityError(TransformLogError):
    """Cross-binding/provenance inconsistency. Fail-fast."""


@dataclass(frozen=True)
class TransformRecord:
    """One successfully applied transformation as deterministic provenance."""

    transform_log_version: str
    patcher_version: str
    operation_ref: str
    operation_plan_ref: str
    decision_ref: str
    profile_ref: ProfileRef
    rule_ref: RuleRef
    target: OperationTarget
    precondition_observed: Any
    desired_value: Any
    input_package_sha256: str
    output_package_sha256: str
    changed_part: str

    def __post_init__(self) -> None:
        if self.transform_log_version != TRANSFORM_LOG_VERSION:
            raise ValueError("unsupported transform_log_version")
        if self.patcher_version != PATCHER_VERSION:
            raise ValueError("unsupported patcher_version")
        for name in (
            "operation_ref",
            "operation_plan_ref",
            "decision_ref",
            "input_package_sha256",
            "output_package_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256_RE.match(value):
                raise ValueError(f"TransformRecord.{name} must be 64 lowercase hex chars")
        if not isinstance(self.profile_ref, ProfileRef):
            raise TypeError("profile_ref must be ProfileRef")
        if not isinstance(self.rule_ref, RuleRef):
            raise TypeError("rule_ref must be RuleRef")
        if not isinstance(self.target, OperationTarget):
            raise TypeError("target must be OperationTarget")
        if self.precondition_observed is None:
            raise ValueError("precondition_observed is mandatory")
        if self.desired_value is None:
            raise ValueError("desired_value is mandatory")
        if self.precondition_observed == self.desired_value:
            raise ValueError("precondition_observed must differ from desired_value")
        if self.rule_ref.profile_id != self.profile_ref.profile_id:
            raise ValueError("rule_ref/profile_ref profile_id mismatch")
        if self.rule_ref.profile_version != self.profile_ref.profile_version:
            raise ValueError("rule_ref/profile_ref profile_version mismatch")
        if self.rule_ref.aspect_id != self.target.aspect_id:
            raise ValueError("rule_ref aspect_id must match target aspect_id")
        if self.changed_part != "word/document.xml":
            raise ValueError("TransformLog v0.1 only records word/document.xml changes")
