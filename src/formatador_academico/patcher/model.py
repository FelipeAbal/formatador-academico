"""Patcher v0.1 — public immutable models and error model.

Contract: docs/decisions/0028-patcher-v01-contract.md (§17 PatchResult,
§18 Error model).

PatchResult is the only output of the patcher. It is frozen, carries package
fingerprints on both sides, and enforces the applied/rejected invariants of
the contract at construction time.

Three failure tiers (rejected is NOT an exception):
1. contract/integrity failure -> fail-fast exception
   (PatcherContractError / PatcherIntegrityError);
2. ordinary rejection -> status=rejected with one closed-vocabulary reason;
3. applied -> output bytes + sha256, changed_part == word/document.xml.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

PATCHER_VERSION = "0.1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

DOCUMENT_PART = "word/document.xml"


class PatcherError(Exception):
    """Base class for all Patcher failures."""


class PatcherContractError(PatcherError, ValueError):
    """API misuse or malformed input artifact. Fail-fast."""


class PatcherIntegrityError(PatcherError):
    """Execution-integrity failure after a matching snapshot fingerprint.

    Path/physical-hash drift, serializer loss, postcondition divergence or
    package-scope violation are NEVER ordinary rejections: they indicate an
    internal contract breach and fail fast.
    """


class PatchStatus(str, Enum):
    APPLIED = "applied"
    REJECTED = "rejected"


class PatchReason(str, Enum):
    """Closed v0.1 rejection vocabulary (decision 0028 §18).

    Any semantic change requires a Patcher version bump. There is no
    `internal_error` reason: unexpected failures are exceptions.
    """

    SNAPSHOT_HASH_MISMATCH = "snapshot_hash_mismatch"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    NONCANONICAL_RUN_PROPERTIES = "noncanonical_run_properties"
    DUPLICATE_TARGET_PROPERTY = "duplicate_target_property"
    UNREPRESENTABLE_VALUE = "unrepresentable_value"


@dataclass(frozen=True)
class PatchResult:
    """Outcome of `apply_cleared_operation`.

    Invariants (decision 0028 §17):
    - applied:  output bytes + sha required, reason None,
                changed_part == "word/document.xml";
    - rejected: no output bytes/sha, reason required, changed_part None.
    """

    patcher_version: str
    status: PatchStatus
    operation_ref: str
    operation_plan_ref: str
    input_package_sha256: str
    output_package_sha256: str | None
    output_package_bytes: bytes | None
    reason: PatchReason | None
    changed_part: str | None

    def __post_init__(self) -> None:
        if self.patcher_version != PATCHER_VERSION:
            raise ValueError("unsupported patcher_version")
        if not isinstance(self.status, PatchStatus):
            raise TypeError("PatchResult.status must be PatchStatus")
        for name in ("operation_ref", "operation_plan_ref", "input_package_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256_RE.match(value):
                raise ValueError(f"PatchResult.{name} must be 64 lowercase hex chars")

        if self.status is PatchStatus.APPLIED:
            if not isinstance(self.output_package_bytes, bytes) or not self.output_package_bytes:
                raise ValueError("applied PatchResult requires output_package_bytes")
            if not isinstance(self.output_package_sha256, str) or not _SHA256_RE.match(
                self.output_package_sha256
            ):
                raise ValueError("applied PatchResult requires output_package_sha256")
            if self.changed_part != DOCUMENT_PART:
                raise ValueError("applied PatchResult requires changed_part == word/document.xml")
            if self.reason is not None:
                raise ValueError("applied PatchResult requires reason None")
        else:
            if self.output_package_bytes is not None:
                raise ValueError("rejected PatchResult carries no output_package_bytes")
            if self.output_package_sha256 is not None:
                raise ValueError("rejected PatchResult carries no output_package_sha256")
            if self.changed_part is not None:
                raise ValueError("rejected PatchResult carries no changed_part")
            if not isinstance(self.reason, PatchReason):
                raise ValueError("rejected PatchResult requires a closed-vocabulary reason")
