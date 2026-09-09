"""Review/Highlight DOCX v0.1 immutable result models (decision 0036)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

from ..docx_parser import PARSER_VERSION
from ..processing_report import PROCESSING_REPORT_VERSION

REVIEW_DOCX_VERSION = "0.1"
DOCUMENT_PART = "word/document.xml"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReviewDocxError(Exception):
    """Base class for Review DOCX failures."""


class ReviewDocxContractError(ReviewDocxError, ValueError):
    """Malformed API input."""


class ReviewDocxIntegrityError(ReviewDocxError):
    """Impossible cross-artifact drift or failed conservation proof."""


class ReviewMarkStatus(str, Enum):
    MARKED = "marked"
    UNMARKED = "unmarked"


class ReviewMarkReason(str, Enum):
    EXISTING_HIGHLIGHT = "existing_highlight"
    NONCANONICAL_RUN_PROPERTIES = "noncanonical_run_properties"
    NO_VISUAL_SURFACE = "no_visual_surface"
    PROTECTED_REVISION_RUN = "protected_revision_run"


def _require_sha(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be 64 lowercase hex chars")


@dataclass(frozen=True)
class ReviewMarkResult:
    target_type: str
    structural_path: str
    physical_hash: str
    status: ReviewMarkStatus
    reason: ReviewMarkReason | None
    source_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.target_type != "run":
            raise ValueError("ReviewMarkResult.target_type must be run")
        if not isinstance(self.structural_path, str) or not self.structural_path:
            raise ValueError("structural_path must be non-empty")
        _require_sha("physical_hash", self.physical_hash)
        if not isinstance(self.status, ReviewMarkStatus):
            raise TypeError("status must be ReviewMarkStatus")
        if self.status is ReviewMarkStatus.MARKED and self.reason is not None:
            raise ValueError("marked result must not have reason")
        if self.status is ReviewMarkStatus.UNMARKED and not isinstance(self.reason, ReviewMarkReason):
            raise ValueError("unmarked result requires ReviewMarkReason")
        allowed = ("applied_change", "unapplied_change", "review_item")
        if (
            not isinstance(self.source_kinds, tuple)
            or not self.source_kinds
            or any(x not in allowed for x in self.source_kinds)
            or tuple(x for x in allowed if x in self.source_kinds) != self.source_kinds
        ):
            raise ValueError("source_kinds must be non-empty and in canonical order")


@dataclass(frozen=True)
class ReviewDocxResult:
    review_docx_version: str
    parser_version: str
    processing_report_version: str
    processing_report_ref: str
    changed_part: str
    input_clean_package_sha256: str
    output_review_package_sha256: str
    output_review_package_bytes: bytes
    mark_results: tuple[ReviewMarkResult, ...]
    unmarkable_classification_item_count: int

    def __post_init__(self) -> None:
        if self.review_docx_version != REVIEW_DOCX_VERSION:
            raise ValueError("unexpected review_docx_version")
        if self.parser_version != PARSER_VERSION:
            raise ValueError("unexpected parser_version")
        if self.processing_report_version != PROCESSING_REPORT_VERSION:
            raise ValueError("unexpected processing_report_version")
        _require_sha("processing_report_ref", self.processing_report_ref)
        if self.changed_part != DOCUMENT_PART:
            raise ValueError("changed_part must be word/document.xml")
        _require_sha("input_clean_package_sha256", self.input_clean_package_sha256)
        _require_sha("output_review_package_sha256", self.output_review_package_sha256)
        if not isinstance(self.output_review_package_bytes, bytes):
            raise TypeError("output_review_package_bytes must be bytes")
        if hashlib.sha256(self.output_review_package_bytes).hexdigest() != self.output_review_package_sha256:
            raise ValueError("output_review_package_sha256 does not match bytes")
        if not isinstance(self.mark_results, tuple) or not all(
            isinstance(x, ReviewMarkResult) for x in self.mark_results
        ):
            raise TypeError("mark_results must be tuple[ReviewMarkResult, ...]")
        if type(self.unmarkable_classification_item_count) is not int or self.unmarkable_classification_item_count < 0:
            raise ValueError("unmarkable_classification_item_count must be non-negative int")
