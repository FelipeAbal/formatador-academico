"""Deterministic TransformLog v0.1 serialization."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from enum import Enum
from typing import Any

from .model import TransformRecord


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in sorted(value.items())}
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    return value


def serialize_transform_record(record: TransformRecord) -> bytes:
    if not isinstance(record, TransformRecord):
        raise TypeError("record must be TransformRecord")
    return json.dumps(
        _jsonable(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def transform_ref(record: TransformRecord) -> str:
    return hashlib.sha256(serialize_transform_record(record)).hexdigest()
