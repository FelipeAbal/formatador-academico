"""TransformLog v0.1 construction and cross-binding (decision 0030)."""
from __future__ import annotations

import hashlib
from decimal import Decimal

from ..decision.model import Actionability, Decision
from ..decision.serialization import serialize_decision
from ..operation_plan.model import LengthValue, OperationKind
from ..operation_plan.serialization import operation_ref as canonical_operation_ref
from ..patcher.model import PATCHER_VERSION, PatchResult, PatchStatus
from ..safety_gate.model import GateClearedOperation
from .model import (
    TRANSFORM_LOG_VERSION,
    TransformLogContractError,
    TransformLogIntegrityError,
    TransformRecord,
)

_SUPPORTED_SLICE = frozenset({("run", "P1", "bold"), ("run", "P2", "font_size")})


def _decision_ref(decision: Decision) -> str:
    return hashlib.sha256(serialize_decision(decision)).hexdigest()


def _operation_semantic_value(property_slot: str, decision_value):
    """Project a Decision value into the frozen OperationPlan semantic type.

    OperationPlan v0.1 deliberately wraps font_size Decimal values in
    LengthValue(pt); bold remains an exact bool. This is provenance
    validation only: no rule, desired value or compliance is recomputed here.
    """

    if property_slot == "font_size":
        if type(decision_value) is not Decimal:
            raise TransformLogIntegrityError(
                "font_size source Decision value must be Decimal under frozen planner contract"
            )
        return LengthValue(value=decision_value, unit="pt")
    if property_slot == "bold":
        if type(decision_value) is not bool:
            raise TransformLogIntegrityError(
                "bold source Decision value must be bool under frozen planner contract"
            )
        return decision_value
    raise TransformLogContractError("property slot is outside TransformLog v0.1")


def build_transform_record(
    cleared_operation: GateClearedOperation,
    patch_result: PatchResult,
    source_decision: Decision,
) -> TransformRecord:
    """Build one applied-only forensic record without DOCX/XML/package IO."""

    if not isinstance(cleared_operation, GateClearedOperation):
        raise TransformLogContractError("cleared_operation must be GateClearedOperation")
    if not isinstance(patch_result, PatchResult):
        raise TransformLogContractError("patch_result must be PatchResult")
    if not isinstance(source_decision, Decision):
        raise TransformLogContractError("source_decision must be Decision")
    if patch_result.status is not PatchStatus.APPLIED:
        raise TransformLogContractError("TransformRecord exists only for APPLIED PatchResult")
    if patch_result.patcher_version != PATCHER_VERSION:
        raise TransformLogContractError("unsupported PatchResult patcher_version")

    operation = cleared_operation.operation
    key = operation.key
    if (
        operation.kind is not OperationKind.SET_PROPERTY
        or (key.target_type, key.aspect_id, key.property_slot) not in _SUPPORTED_SLICE
    ):
        raise TransformLogContractError("operation is outside TransformLog v0.1 applied slice")

    if cleared_operation.operation_ref != canonical_operation_ref(operation):
        raise TransformLogIntegrityError("cleared operation_ref does not bind its operation")
    if patch_result.operation_ref != cleared_operation.operation_ref:
        raise TransformLogIntegrityError("PatchResult operation_ref mismatch")
    if patch_result.operation_plan_ref != cleared_operation.operation_plan_ref:
        raise TransformLogIntegrityError("PatchResult operation_plan_ref mismatch")
    if patch_result.input_package_sha256 != cleared_operation.current_package_sha256:
        raise TransformLogIntegrityError("PatchResult input package SHA mismatch")

    decision_ref = _decision_ref(source_decision)
    if decision_ref != operation.decision_ref:
        raise TransformLogIntegrityError("source Decision does not match operation decision_ref")
    if source_decision.actionability is not Actionability.DETERMINISTIC_CHANGE:
        raise TransformLogIntegrityError("source Decision is not deterministic_change")
    if source_decision.rule_ref is None:
        raise TransformLogIntegrityError("applied transformation source Decision must carry RuleRef")

    dt = source_decision.target
    ot = operation.target
    target_fields = (
        "target_type",
        "structural_path",
        "physical_hash",
        "target_class",
        "aspect_id",
        "property_slot",
    )
    if any(getattr(dt, name) != getattr(ot, name) for name in target_fields):
        raise TransformLogIntegrityError("source Decision target does not match operation target")

    expected_observed = _operation_semantic_value(
        operation.key.property_slot, source_decision.observed
    )
    expected_desired = _operation_semantic_value(
        operation.key.property_slot, source_decision.desired_value
    )
    if expected_observed != operation.precondition_observed:
        raise TransformLogIntegrityError("source Decision observed does not match operation precondition")
    if expected_desired != operation.desired_value:
        raise TransformLogIntegrityError("source Decision desired_value does not match operation")

    if source_decision.profile_ref.profile_id != source_decision.rule_ref.profile_id:
        raise TransformLogIntegrityError("source Decision profile/rule profile_id mismatch")
    if source_decision.profile_ref.profile_version != source_decision.rule_ref.profile_version:
        raise TransformLogIntegrityError("source Decision profile/rule profile_version mismatch")
    if source_decision.rule_ref.aspect_id != operation.target.aspect_id:
        raise TransformLogIntegrityError("source Decision rule aspect does not match operation target")

    if patch_result.output_package_sha256 is None or patch_result.changed_part is None:
        raise TransformLogIntegrityError("APPLIED PatchResult lacks required frozen output provenance")

    return TransformRecord(
        transform_log_version=TRANSFORM_LOG_VERSION,
        patcher_version=patch_result.patcher_version,
        operation_ref=patch_result.operation_ref,
        operation_plan_ref=patch_result.operation_plan_ref,
        decision_ref=decision_ref,
        profile_ref=source_decision.profile_ref,
        rule_ref=source_decision.rule_ref,
        target=operation.target,
        precondition_observed=operation.precondition_observed,
        desired_value=operation.desired_value,
        input_package_sha256=patch_result.input_package_sha256,
        output_package_sha256=patch_result.output_package_sha256,
        changed_part=patch_result.changed_part,
    )
