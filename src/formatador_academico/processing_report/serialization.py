"""Canonical serialization for Processing Report v0.1."""
from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from .model import ProcessingReport


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        raise TypeError("Processing Report serialization must not contain bytes")
    if isinstance(value, tuple):
        return [_to_jsonable(x) for x in value]
    if isinstance(value, list):
        return [_to_jsonable(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if is_dataclass(value):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(value)}
    raise TypeError(f"unsupported Processing Report serialization type: {type(value)!r}")


def serialize_processing_report(report: ProcessingReport) -> bytes:
    if not isinstance(report, ProcessingReport):
        raise TypeError("report must be ProcessingReport")
    payload = _to_jsonable(report)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def processing_report_ref(report: ProcessingReport) -> str:
    return hashlib.sha256(serialize_processing_report(report)).hexdigest()
