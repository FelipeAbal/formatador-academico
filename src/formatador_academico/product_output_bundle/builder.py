"""Product Output Bundle v0.1 builder (decision 0038)."""
from __future__ import annotations

import hashlib

from ..processing_report import (
    PROCESSING_REPORT_VERSION,
    ProcessingReportContractError,
    ProcessingReportIntegrityError,
    build_processing_report,
    processing_report_ref,
    serialize_processing_report,
)
from ..processing_session import (
    DEFAULT_MAX_APPLIED_OPERATIONS,
    PROCESSING_SESSION_VERSION,
    ProcessingProfile,
    ProcessingSessionContractError,
    ProcessingSessionIntegrityError,
    process_document,
)
from ..review_docx import (
    REVIEW_DOCX_VERSION,
    ReviewDocxContractError,
    ReviewDocxIntegrityError,
    build_review_docx,
)
from .model import (
    PRODUCT_OUTPUT_BUNDLE_VERSION,
    ProductOutputBundle,
    ProductOutputBundleContractError,
    ProductOutputBundleIntegrityError,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_bundle_lineage(package_snapshot: bytes, session, report, report_bytes: bytes, review) -> None:
    input_sha = _sha(package_snapshot)
    clean_sha = _sha(session.output_package_bytes)
    report_ref = _sha(report_bytes)
    review_sha = _sha(review.output_review_package_bytes)

    if input_sha != session.input_package_sha256:
        raise ProductOutputBundleIntegrityError("session input SHA does not match supplied package snapshot")
    if clean_sha != session.output_package_sha256:
        raise ProductOutputBundleIntegrityError("session clean SHA does not match clean package bytes")
    if report.summary.input_package_sha256 != session.input_package_sha256:
        raise ProductOutputBundleIntegrityError("report input SHA does not match session input SHA")
    if report.summary.output_package_sha256 != clean_sha:
        raise ProductOutputBundleIntegrityError("report output SHA does not match clean package SHA")
    if serialize_processing_report(report) != report_bytes:
        raise ProductOutputBundleIntegrityError("report JSON bytes are not the canonical serialization")
    if processing_report_ref(report) != report_ref:
        raise ProductOutputBundleIntegrityError("processing report ref does not match report JSON bytes")
    if review.input_clean_package_sha256 != clean_sha:
        raise ProductOutputBundleIntegrityError("review input SHA does not match clean package SHA")
    if review.processing_report_ref != report_ref:
        raise ProductOutputBundleIntegrityError("review report ref does not match processing report ref")
    if review.output_review_package_sha256 != review_sha:
        raise ProductOutputBundleIntegrityError("review output SHA does not match review package bytes")
    if session.processing_session_version != PROCESSING_SESSION_VERSION:
        raise ProductOutputBundleIntegrityError("unexpected Processing Session version")
    if report.processing_report_version != PROCESSING_REPORT_VERSION:
        raise ProductOutputBundleIntegrityError("unexpected Processing Report version")
    if review.review_docx_version != REVIEW_DOCX_VERSION:
        raise ProductOutputBundleIntegrityError("unexpected Review DOCX version")


def build_product_output_bundle(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = DEFAULT_MAX_APPLIED_OPERATIONS,
) -> ProductOutputBundle:
    """Run the frozen product pipeline and return all three bound artifacts."""

    if not isinstance(package_snapshot, bytes):
        raise ProductOutputBundleContractError("package_snapshot must be bytes")
    if not isinstance(profile, ProcessingProfile):
        raise ProductOutputBundleContractError("profile must be ProcessingProfile")

    try:
        session = process_document(
            package_snapshot,
            profile,
            max_applied_operations=max_applied_operations,
        )
    except ProcessingSessionContractError as exc:
        raise ProductOutputBundleContractError(str(exc)) from exc
    except ProcessingSessionIntegrityError as exc:
        raise ProductOutputBundleIntegrityError(str(exc)) from exc

    try:
        report = build_processing_report(session)
        report_bytes = serialize_processing_report(report)
    except ProcessingReportContractError as exc:
        raise ProductOutputBundleContractError(str(exc)) from exc
    except ProcessingReportIntegrityError as exc:
        raise ProductOutputBundleIntegrityError(str(exc)) from exc

    try:
        review = build_review_docx(session.output_package_bytes, report)
    except ReviewDocxContractError as exc:
        raise ProductOutputBundleContractError(str(exc)) from exc
    except ReviewDocxIntegrityError as exc:
        raise ProductOutputBundleIntegrityError(str(exc)) from exc

    _validate_bundle_lineage(package_snapshot, session, report, report_bytes, review)

    return ProductOutputBundle(
        product_output_bundle_version=PRODUCT_OUTPUT_BUNDLE_VERSION,
        processing_session_version=PROCESSING_SESSION_VERSION,
        processing_report_version=PROCESSING_REPORT_VERSION,
        review_docx_version=REVIEW_DOCX_VERSION,
        profile_ref=session.profile_ref,
        session_status=session.status,
        input_package_sha256=session.input_package_sha256,
        clean_package_sha256=session.output_package_sha256,
        clean_package_bytes=session.output_package_bytes,
        review_package_sha256=review.output_review_package_sha256,
        review_package_bytes=review.output_review_package_bytes,
        processing_report_ref=processing_report_ref(report),
        processing_report_json_bytes=report_bytes,
        processing_report=report,
    )
