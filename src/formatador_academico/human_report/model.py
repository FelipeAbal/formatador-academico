"""Human-readable Processing Report v0.1 public model (decision 0045)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

HUMAN_REPORT_VERSION = "0.1"
HUMAN_REPORT_MEDIA_TYPE = "text/markdown; charset=utf-8"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class HumanReportError(Exception):
    """Base human-report error."""


class HumanReportContractError(HumanReportError, ValueError):
    """Public API misuse."""


class HumanReportIntegrityError(HumanReportError):
    """Impossible renderer/report inconsistency."""


@dataclass(frozen=True)
class RenderedProcessingReport:
    human_report_version: str
    processing_report_ref: str
    media_type: str
    content_bytes: bytes
    content_sha256: str

    def __post_init__(self) -> None:
        if self.human_report_version != HUMAN_REPORT_VERSION:
            raise ValueError("unsupported human_report_version")
        if not isinstance(self.processing_report_ref, str) or not _SHA256_RE.fullmatch(self.processing_report_ref):
            raise ValueError("processing_report_ref must be lowercase sha256")
        if self.media_type != HUMAN_REPORT_MEDIA_TYPE:
            raise ValueError("unexpected human report media_type")
        if type(self.content_bytes) is not bytes:
            raise TypeError("content_bytes must be exact bytes")
        if self.content_bytes.startswith(b"\xef\xbb\xbf"):
            raise ValueError("human report must not contain UTF-8 BOM")
        try:
            text = self.content_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("human report content must be strict UTF-8") from exc
        if "\r" in text:
            raise ValueError("human report must use canonical LF newlines")
        if not text.endswith("\n") or text.endswith("\n\n"):
            raise ValueError("human report must end with exactly one newline")
        if not isinstance(self.content_sha256, str) or not _SHA256_RE.fullmatch(self.content_sha256):
            raise ValueError("content_sha256 must be lowercase sha256")
        if hashlib.sha256(self.content_bytes).hexdigest() != self.content_sha256:
            raise ValueError("content_sha256 does not match content_bytes")
