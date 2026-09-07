"""Deterministic OperationPlan v0.1 serialization.

Same canonical pattern as the frozen Decision serialization: dataclasses
frozen, enums -> string, Decimal -> string, tuple -> array, sort_keys,
compact separators, UTF-8, no timestamps.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from enum import Enum
from typing import Any

from .model import OperationPlan, PlannedOperation, PlanningResult


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


def _serialize(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def serialize_planning_result(result: PlanningResult) -> bytes:
    return _serialize(result)


def serialize_planning_results(results: tuple[PlanningResult, ...]) -> bytes:
    return _serialize(results)


def serialize_operation_plan(plan: OperationPlan) -> bytes:
    return _serialize(plan)


def serialize_planned_operation(operation: PlannedOperation) -> bytes:
    """Canonical deterministic serialization of a single PlannedOperation.

    Uses the exact same canonical scheme as the frozen plan serialization
    (enums -> str, Decimal -> str, tuple -> array, sort_keys, compact
    separators, UTF-8). Additive helper for SafetyGate v0.1 (decision 0026);
    does not alter any frozen serialization result.
    """

    return _serialize(operation)


def operation_ref(operation: PlannedOperation) -> str:
    """Deterministic derived reference of a PlannedOperation (no UUIDs)."""

    return hashlib.sha256(serialize_planned_operation(operation)).hexdigest()


def operation_plan_ref(plan: OperationPlan) -> str:
    """Deterministic derived reference: sha256(serialize_operation_plan(plan))."""

    return hashlib.sha256(serialize_operation_plan(plan)).hexdigest()
