"""Deterministic Classification Layer serialization.

Enum -> string, tuple -> array, sort_keys, UTF-8, no timestamps, no numeric
confidence, no live objects. Same input -> identical bytes, across processes
and hash seeds.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from .model import ClassificationResult


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in sorted(value.items())}
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    return value


def _serialize(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def serialize_classification_result(result: ClassificationResult) -> bytes:
    return _serialize(result)


def serialize_classification_results(results: tuple[ClassificationResult, ...]) -> bytes:
    return _serialize(results)


def classification_result_to_json(result: ClassificationResult) -> str:
    return serialize_classification_result(result).decode("utf-8")
