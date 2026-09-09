"""Product Output Bundle v0.1 immutable public model (decision 0038)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..decision.model import ProfileRef
from ..processing_report import PROCESSING_REPORT_VERSION, ProcessingReport
from ..processing_session import PROCESSING_SESSION_VERSION, ProcessingSessionStatus
from ..review_docx import REVIEW_DOCX_VERSION

PRODUCT_OUTPUT_BUNDLE_VERSION = "0.1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProductOutputBundleError(Exception):
    """Base class for the product output boundary."""


class ProductOutputBundleContractError(ProductOutputBundleError, ValueError):
    """Malformed product-boundary input or upstream contract failure."""


class ProductOutputBundleIntegrityError(ProductOutputBundleError):
    """Cross-artifact lineage/hash/version contradiction."""


def _require_sha(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be 64 lowercase hex chars")


@dataclass(frozen=True)
class ProductOutputBundle:
    product_output_bundle_version: str
    processing_session_version: str
    processing_report_version: str
    review_docx_version: str
    profile_ref: ProfileRef
    session_status: ProcessingSessionStatus
    input_package_sha256: str
    clean_package_sha256: str
    clean_package_bytes: bytes
    review_package_sha256: str
    review_package_bytes: bytes
    processing_report_ref: str
    processing_report_json_bytes: bytes
    processing_report: ProcessingReport

    def __post_init__(self) -> None:
        if self.product_output_bundle_version != PRODUCT_OUTPUT_BUNDLE_VERSION:
            raise ValueError("unexpected product_output_bundle_version")
        if self.processing_session_version != PROCESSING_SESSION_VERSION:
            raise ValueError("unexpected processing_session_version")
        if self.processing_report_version != PROCESSING_REPORT_VERSION:
            raise ValueError("unexpected processing_report_version")
        if self.review_docx_version != REVIEW_DOCX_VERSION:
            raise ValueError("unexpected review_docx_version")
        if not isinstance(self.profile_ref, ProfileRef):
            raise TypeError("profile_ref must be ProfileRef")
        if not isinstance(self.session_status, ProcessingSessionStatus):
            raise TypeError("session_status must be ProcessingSessionStatus")
        for name in (
            "input_package_sha256",
            "clean_package_sha256",
            "review_package_sha256",
            "processing_report_ref",
        ):
            _require_sha(name, getattr(self, name))
        if not isinstance(self.clean_package_bytes, bytes) or not self.clean_package_bytes:
            raise ValueError("clean_package_bytes must be non-empty bytes")
        if hashlib.sha256(self.clean_package_bytes).hexdigest() != self.clean_package_sha256:
            raise ValueError("clean_package_sha256 does not match clean_package_bytes")
        if not isinstance(self.review_package_bytes, bytes) or not self.review_package_bytes:
            raise ValueError("review_package_bytes must be non-empty bytes")
        if hashlib.sha256(self.review_package_bytes).hexdigest() != self.review_package_sha256:
            raise ValueError("review_package_sha256 does not match review_package_bytes")
        if not isinstance(self.processing_report_json_bytes, bytes) or not self.processing_report_json_bytes:
            raise ValueError("processing_report_json_bytes must be non-empty bytes")
        if hashlib.sha256(self.processing_report_json_bytes).hexdigest() != self.processing_report_ref:
            raise ValueError("processing_report_ref does not match processing_report_json_bytes")
        if not isinstance(self.processing_report, ProcessingReport):
            raise TypeError("processing_report must be ProcessingReport")

        # Public-model self-binding: callers cannot fabricate a Bundle whose
        # typed report disagrees with the material JSON or with the product
        # lineage fields, even if they bypass the canonical builder.
        from ..processing_report import serialize_processing_report

        if serialize_processing_report(self.processing_report) != self.processing_report_json_bytes:
            raise ValueError("processing_report does not match processing_report_json_bytes")
        if self.processing_report.processing_report_version != self.processing_report_version:
            raise ValueError("processing_report version mismatch")
        if self.processing_report.processing_session_version != self.processing_session_version:
            raise ValueError("processing_report session version mismatch")
        if self.processing_report.profile_ref != self.profile_ref:
            raise ValueError("processing_report profile_ref mismatch")
        if self.processing_report.summary.session_status is not self.session_status:
            raise ValueError("processing_report session_status mismatch")
        if self.processing_report.summary.input_package_sha256 != self.input_package_sha256:
            raise ValueError("processing_report input SHA mismatch")
        if self.processing_report.summary.output_package_sha256 != self.clean_package_sha256:
            raise ValueError("processing_report output SHA mismatch")
