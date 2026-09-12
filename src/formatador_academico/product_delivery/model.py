"""Product Delivery / File Naming v0.1 immutable models (decision 0047)."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum

PRODUCT_DELIVERY_VERSION = "0.1"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
JSON_MEDIA_TYPE = "application/json; charset=utf-8"
MARKDOWN_MEDIA_TYPE = "text/markdown; charset=utf-8"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProductDeliveryError(Exception):
    """Base Product Delivery error."""


class ProductDeliveryContractError(ProductDeliveryError, ValueError):
    """Malformed delivery-boundary input."""


class ProductDeliveryIntegrityError(ProductDeliveryError):
    """Impossible cross-artifact/manifest inconsistency."""


class DeliveryRole(str, Enum):
    CLEAN_DOCX = "clean_docx"
    REVIEW_DOCX = "review_docx"
    TECHNICAL_REPORT = "technical_report"
    HUMAN_REPORT = "human_report"
    MANIFEST = "manifest"


ROLE_ORDER = (
    DeliveryRole.CLEAN_DOCX,
    DeliveryRole.REVIEW_DOCX,
    DeliveryRole.TECHNICAL_REPORT,
    DeliveryRole.HUMAN_REPORT,
    DeliveryRole.MANIFEST,
)

_SUFFIX_BY_ROLE = {
    DeliveryRole.CLEAN_DOCX: "_limpo.docx",
    DeliveryRole.REVIEW_DOCX: "_revisao.docx",
    DeliveryRole.TECHNICAL_REPORT: "_relatorio.json",
    DeliveryRole.HUMAN_REPORT: "_relatorio.md",
    DeliveryRole.MANIFEST: "_manifest.json",
}
_MEDIA_BY_ROLE = {
    DeliveryRole.CLEAN_DOCX: DOCX_MEDIA_TYPE,
    DeliveryRole.REVIEW_DOCX: DOCX_MEDIA_TYPE,
    DeliveryRole.TECHNICAL_REPORT: JSON_MEDIA_TYPE,
    DeliveryRole.HUMAN_REPORT: MARKDOWN_MEDIA_TYPE,
    DeliveryRole.MANIFEST: JSON_MEDIA_TYPE,
}


def filename_for_role(base_name: str, role: DeliveryRole) -> str:
    if not isinstance(base_name, str) or not base_name:
        raise ValueError("base_name must be non-empty str")
    if not isinstance(role, DeliveryRole):
        raise TypeError("role must be DeliveryRole")
    return base_name + _SUFFIX_BY_ROLE[role]


def media_type_for_role(role: DeliveryRole) -> str:
    if not isinstance(role, DeliveryRole):
        raise TypeError("role must be DeliveryRole")
    return _MEDIA_BY_ROLE[role]


@dataclass(frozen=True)
class DeliveryFile:
    role: DeliveryRole
    filename: str
    media_type: str
    content_bytes: bytes
    content_sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.role, DeliveryRole):
            raise TypeError("DeliveryFile.role must be DeliveryRole")
        if not isinstance(self.filename, str) or not self.filename:
            raise ValueError("DeliveryFile.filename must be non-empty")
        if "/" in self.filename or "\\" in self.filename or self.filename.startswith("."):
            raise ValueError("DeliveryFile.filename must be a simple non-hidden name")
        if self.filename.endswith((" ", ".")) or len(self.filename) > 140:
            raise ValueError("DeliveryFile.filename violates safety bounds")
        if self.media_type != media_type_for_role(self.role):
            raise ValueError("DeliveryFile.media_type does not match role")
        if type(self.content_bytes) is not bytes:
            raise TypeError("DeliveryFile.content_bytes must be exact bytes")
        if not isinstance(self.content_sha256, str) or _SHA256_RE.fullmatch(self.content_sha256) is None:
            raise ValueError("DeliveryFile.content_sha256 must be lowercase sha256")
        if hashlib.sha256(self.content_bytes).hexdigest() != self.content_sha256:
            raise ValueError("DeliveryFile.content_sha256 does not match bytes")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("DeliveryFile.size_bytes must be non-negative int")
        if self.size_bytes != len(self.content_bytes):
            raise ValueError("DeliveryFile.size_bytes does not match bytes")


@dataclass(frozen=True)
class ProductDelivery:
    product_delivery_version: str
    base_name: str
    product_output_bundle_ref: str
    human_report_ref: str
    files: tuple[DeliveryFile, ...]

    def __post_init__(self) -> None:
        if self.product_delivery_version != PRODUCT_DELIVERY_VERSION:
            raise ValueError("unsupported product_delivery_version")
        if not isinstance(self.base_name, str) or not self.base_name:
            raise ValueError("ProductDelivery.base_name must be non-empty")
        if self.base_name.startswith(".") or "/" in self.base_name or "\\" in self.base_name:
            raise ValueError("ProductDelivery.base_name is not filename-safe")
        if len(self.base_name) > 100 or self.base_name.endswith((" ", ".")):
            raise ValueError("ProductDelivery.base_name violates canonical bounds")
        for name, value in (
            ("product_output_bundle_ref", self.product_output_bundle_ref),
            ("human_report_ref", self.human_report_ref),
        ):
            if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{name} must be lowercase sha256")
        if not isinstance(self.files, tuple) or not all(isinstance(x, DeliveryFile) for x in self.files):
            raise TypeError("ProductDelivery.files must be tuple[DeliveryFile, ...]")
        if tuple(x.role for x in self.files) != ROLE_ORDER:
            raise ValueError("ProductDelivery files must use exact frozen role order")
        expected_names = tuple(filename_for_role(self.base_name, role) for role in ROLE_ORDER)
        if tuple(x.filename for x in self.files) != expected_names:
            raise ValueError("ProductDelivery filenames do not match canonical base/roles")
        if len(set(expected_names)) != len(expected_names):
            raise ValueError("ProductDelivery filenames must be unique")
        if self.files[3].content_sha256 != self.human_report_ref:
            raise ValueError("human_report_ref does not match human report file")
        self._validate_manifest()

    def _validate_manifest(self) -> None:
        manifest_file = self.files[4]
        try:
            manifest = json.loads(manifest_file.content_bytes.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("manifest must be strict UTF-8 JSON") from exc
        expected = {
            "product_delivery_version": self.product_delivery_version,
            "base_name": self.base_name,
            "product_output_bundle_ref": self.product_output_bundle_ref,
            "human_report_ref": self.human_report_ref,
            "files": [
                {
                    "role": item.role.value,
                    "filename": item.filename,
                    "media_type": item.media_type,
                    "sha256": item.content_sha256,
                    "size_bytes": item.size_bytes,
                }
                for item in self.files[:4]
            ],
        }
        if manifest != expected:
            raise ValueError("manifest does not match ProductDelivery content files")
        canonical = json.dumps(
            expected,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if manifest_file.content_bytes != canonical:
            raise ValueError("manifest bytes are not canonical JSON")
