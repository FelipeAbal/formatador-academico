"""Pure in-memory Product Delivery builder (decision 0047)."""
from __future__ import annotations

import hashlib
import json
import re

from ..human_report import render_processing_report
from ..product_output_bundle import ProductOutputBundle
from .model import (
    DOCX_MEDIA_TYPE,
    JSON_MEDIA_TYPE,
    MARKDOWN_MEDIA_TYPE,
    PRODUCT_DELIVERY_VERSION,
    DeliveryFile,
    DeliveryRole,
    ProductDelivery,
    ProductDeliveryContractError,
    ProductDeliveryIntegrityError,
    filename_for_role,
)

_RESERVED_WINDOWS = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_FORBIDDEN_FILENAME_CHARS = set('/\\:*?"<>|')
_CONTROL_RE = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f]")
_WHITESPACE_RE = re.compile(r"\s+")
_UNDERSCORE_RE = re.compile(r"_+")


def _validate_canonical_base(value: str) -> None:
    if not value or value in {".", ".."} or value.startswith("."):
        raise ProductDeliveryContractError("base_name is empty/hidden/invalid after canonicalization")
    if value.endswith((" ", ".")):
        raise ProductDeliveryContractError("base_name ends with unsafe space/dot")
    first_component = value.split(".", 1)[0].upper()
    if first_component in _RESERVED_WINDOWS:
        raise ProductDeliveryContractError("base_name is a reserved Windows device name")


def canonicalize_delivery_base_name(base_name: str) -> str:
    """Canonicalize explicit delivery metadata without inferring document identity."""
    if type(base_name) is not str:
        raise ProductDeliveryContractError("base_name must be exact str")
    if not (1 <= len(base_name) <= 120):
        raise ProductDeliveryContractError("base_name must contain 1..120 codepoints")
    if "\x00" in base_name:
        raise ProductDeliveryContractError("base_name must not contain NUL")
    if not base_name.strip(" .\t\r\n\f\v"):
        raise ProductDeliveryContractError("base_name must not be only whitespace/dots")

    value = base_name.strip()
    value = "".join("_" if ch in _FORBIDDEN_FILENAME_CHARS else ch for ch in value)
    value = _CONTROL_RE.sub("_", value)
    value = _WHITESPACE_RE.sub(" ", value)
    value = _UNDERSCORE_RE.sub("_", value)
    value = value.rstrip(" .")
    _validate_canonical_base(value)

    if len(value) > 100:
        value = value[:100].rstrip(" .")
        _validate_canonical_base(value)
    return value


def _canonical_json_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def product_output_bundle_ref(bundle: ProductOutputBundle) -> str:
    if not isinstance(bundle, ProductOutputBundle):
        raise ProductDeliveryContractError("bundle must be ProductOutputBundle")
    payload = {
        "product_output_bundle_version": bundle.product_output_bundle_version,
        "input_package_sha256": bundle.input_package_sha256,
        "clean_package_sha256": bundle.clean_package_sha256,
        "review_package_sha256": bundle.review_package_sha256,
        "processing_report_ref": bundle.processing_report_ref,
        "profile_id": bundle.profile_ref.profile_id,
        "profile_version": bundle.profile_ref.profile_version,
        "session_status": bundle.session_status.value,
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _delivery_file(role: DeliveryRole, base: str, media_type: str, content: bytes) -> DeliveryFile:
    return DeliveryFile(
        role=role,
        filename=filename_for_role(base, role),
        media_type=media_type,
        content_bytes=content,
        content_sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )


def build_product_delivery(
    bundle: ProductOutputBundle,
    *,
    base_name: str,
) -> ProductDelivery:
    """Build five in-memory delivery files from one frozen ProductOutputBundle."""
    if not isinstance(bundle, ProductOutputBundle):
        raise ProductDeliveryContractError("bundle must be ProductOutputBundle")
    base = canonicalize_delivery_base_name(base_name)

    rendered = render_processing_report(bundle.processing_report)
    if rendered.processing_report_ref != bundle.processing_report_ref:
        raise ProductDeliveryIntegrityError("human report does not bind to bundle ProcessingReport")

    bundle_ref = product_output_bundle_ref(bundle)
    content_files = (
        _delivery_file(DeliveryRole.CLEAN_DOCX, base, DOCX_MEDIA_TYPE, bundle.clean_package_bytes),
        _delivery_file(DeliveryRole.REVIEW_DOCX, base, DOCX_MEDIA_TYPE, bundle.review_package_bytes),
        _delivery_file(DeliveryRole.TECHNICAL_REPORT, base, JSON_MEDIA_TYPE, bundle.processing_report_json_bytes),
        _delivery_file(DeliveryRole.HUMAN_REPORT, base, MARKDOWN_MEDIA_TYPE, rendered.content_bytes),
    )

    manifest_payload = {
        "product_delivery_version": PRODUCT_DELIVERY_VERSION,
        "base_name": base,
        "product_output_bundle_ref": bundle_ref,
        "human_report_ref": rendered.content_sha256,
        "files": [
            {
                "role": item.role.value,
                "filename": item.filename,
                "media_type": item.media_type,
                "sha256": item.content_sha256,
                "size_bytes": item.size_bytes,
            }
            for item in content_files
        ],
    }
    manifest_bytes = _canonical_json_bytes(manifest_payload)
    manifest_file = _delivery_file(DeliveryRole.MANIFEST, base, JSON_MEDIA_TYPE, manifest_bytes)

    try:
        return ProductDelivery(
            product_delivery_version=PRODUCT_DELIVERY_VERSION,
            base_name=base,
            product_output_bundle_ref=bundle_ref,
            human_report_ref=rendered.content_sha256,
            files=content_files + (manifest_file,),
        )
    except (TypeError, ValueError) as exc:
        raise ProductDeliveryIntegrityError("constructed ProductDelivery failed invariants") from exc
