"""Deterministic SafetyGate v0.1 serialization.

Same canonical project pattern: frozen dataclasses, enums -> str,
Decimal -> str, tuple -> array, sort_keys, compact separators, UTF-8, no
timestamps, no randomness.
"""

from __future__ import annotations

import json
from decimal import Decimal
from enum import Enum
from typing import Any

from .model import GateClearedOperation, GateResult, SafetyGateReport


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
    if isinstance(value, GateClearedOperation):
        # The emission `_proof` is a process-local object and never serializes.
        return {
            "operation": _jsonable(value.operation),
            "operation_ref": value.operation_ref,
            "operation_plan_ref": value.operation_plan_ref,
            "current_package_sha256": value.current_package_sha256,
        }
    if hasattr(value, "__dataclass_fields__"):
        # Field-wise recursion (not asdict) so nested GateClearedOperation
        # values keep the proof-excluding serialization above.
        return {k: _jsonable(getattr(value, k)) for k in value.__dataclass_fields__}
    return value


def _serialize(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def serialize_gate_result(result: GateResult) -> bytes:
    return _serialize(result)


def serialize_safety_gate_report(report: SafetyGateReport) -> bytes:
    return _serialize(report)
