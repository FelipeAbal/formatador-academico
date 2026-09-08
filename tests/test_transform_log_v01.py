"""TransformLog v0.1 contract tests (decision 0030)."""
from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import fields, replace
from decimal import Decimal
from unittest.mock import patch as mock_patch

from formatador_academico.decision.model import (
    Actionability, ComplianceStatus, Decision, DecisionKey, DecisionReason,
    DecisionTarget, ProfileRef, RuleRef,
)
from formatador_academico.decision.serialization import serialize_decision
from formatador_academico.operation_plan.model import (
    LengthValue, OperationKind, OperationTarget, PlannedOperation,
)
from formatador_academico.operation_plan.serialization import operation_ref
from formatador_academico.patcher.model import PatchReason, PatchResult, PatchStatus
from formatador_academico.safety_gate.model import GateClearedOperation, _EMISSION_PROOF
from formatador_academico.transform_log import (
    TRANSFORM_LOG_VERSION, TransformLogContractError, TransformLogIntegrityError,
    build_transform_record, serialize_transform_record, transform_ref,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decision(*, observed=False, desired=True, target_class="body", slot="bold") -> Decision:
    if slot == "bold":
        aspect, rule_id, path = "P1", "body-bold", "body.bold"
    else:
        aspect, rule_id, path = "P2", "body-font", "body.font_size"
    return Decision(
        decision_version="0.1", decision_vocabulary_version="0.1",
        target=DecisionTarget(
            "run", "/w:document/w:body[1]/w:p[1]/w:r[1]", "a" * 64,
            target_class, aspect, slot,
        ),
        compliance=ComplianceStatus.NON_COMPLIANT,
        actionability=Actionability.DETERMINISTIC_CHANGE,
        reason=DecisionReason.DIFFERS_FROM_RULE,
        analysis_status="resolved", observed=observed, desired_value=desired,
        profile_ref=ProfileRef("journal-x", "3"),
        rule_ref=RuleRef("journal-x", "3", rule_id, aspect, path),
        evidence_ref=None, decision_warnings=(),
    )


def _plan_value(slot: str, value):
    return LengthValue(value, "pt") if slot == "font_size" else value


def _operation_for(decision: Decision, *, target: OperationTarget | None = None,
                   observed_marker=None, desired_marker=None) -> PlannedOperation:
    dt = decision.target
    target = target or OperationTarget(
        dt.target_type, dt.structural_path, dt.physical_hash, dt.target_class,
        dt.aspect_id, dt.property_slot,
    )
    observed = _plan_value(dt.property_slot, decision.observed) if observed_marker is None else observed_marker
    desired = _plan_value(dt.property_slot, decision.desired_value) if desired_marker is None else desired_marker
    return PlannedOperation(
        OperationKind.SET_PROPERTY,
        DecisionKey(dt.target_type, dt.aspect_id, dt.property_slot),
        target, observed, desired, _sha(serialize_decision(decision)),
    )


def _artifacts(decision: Decision | None = None, operation: PlannedOperation | None = None):
    decision = decision or _decision()
    operation = operation or _operation_for(decision)
    op_ref = operation_ref(operation)
    token = GateClearedOperation(
        operation, op_ref, "b" * 64, "c" * 64, _EMISSION_PROOF,
    )
    output = b"patched-docx-placeholder"
    patch = PatchResult(
        "0.1", PatchStatus.APPLIED, op_ref, "b" * 64, "c" * 64,
        _sha(output), output, None, "word/document.xml",
    )
    return decision, operation, token, patch


class TransformLogBuildTests(unittest.TestCase):
    def test_valid_applied_build_and_copied_provenance(self):
        d, op, token, patch = _artifacts()
        r = build_transform_record(token, patch, d)
        self.assertEqual(r.transform_log_version, TRANSFORM_LOG_VERSION)
        self.assertEqual(r.patcher_version, patch.patcher_version)
        self.assertEqual(r.operation_ref, token.operation_ref)
        self.assertEqual(r.operation_plan_ref, token.operation_plan_ref)
        self.assertEqual(r.decision_ref, op.decision_ref)
        self.assertEqual(r.profile_ref, d.profile_ref)
        self.assertEqual(r.rule_ref, d.rule_ref)
        self.assertEqual(r.target, op.target)
        self.assertEqual(r.precondition_observed, op.precondition_observed)
        self.assertEqual(r.desired_value, op.desired_value)
        self.assertEqual(r.input_package_sha256, patch.input_package_sha256)
        self.assertEqual(r.output_package_sha256, patch.output_package_sha256)
        self.assertEqual(r.changed_part, patch.changed_part)

    def test_rejected_patch_cannot_build(self):
        d, _, token, patch = _artifacts()
        rejected = PatchResult(
            "0.1", PatchStatus.REJECTED, patch.operation_ref, patch.operation_plan_ref,
            patch.input_package_sha256, None, None, PatchReason.UNSUPPORTED_OPERATION, None,
        )
        with self.assertRaises(TransformLogContractError):
            build_transform_record(token, rejected, d)

    def test_wrong_input_types_fail_contract(self):
        d, op, token, patch = _artifacts()
        for args in ((op, patch, d), (token, object(), d), (token, patch, object())):
            with self.assertRaises(TransformLogContractError):
                build_transform_record(*args)

    def test_patch_cross_bindings_fail_fast(self):
        d, _, token, patch = _artifacts()
        for bad in (
            replace(patch, operation_ref="d" * 64),
            replace(patch, operation_plan_ref="d" * 64),
            replace(patch, input_package_sha256="d" * 64),
        ):
            with self.assertRaises(TransformLogIntegrityError):
                build_transform_record(token, bad, d)

    def test_wrong_source_decision_ref(self):
        _, _, token, patch = _artifacts()
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, patch, _decision(target_class="heading"))

    def test_source_decision_target_must_match_operation(self):
        d = _decision()
        wrong_target = OperationTarget("run", d.target.structural_path, d.target.physical_hash,
                                       "heading", "P1", "bold")
        op = _operation_for(d, target=wrong_target)
        d, _, token, patch = _artifacts(d, op)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, patch, d)

    def test_source_decision_observed_must_match_operation(self):
        d = _decision()
        op = _operation_for(d, observed_marker="unexpected")
        d, _, token, patch = _artifacts(d, op)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, patch, d)

    def test_source_decision_desired_must_match_operation(self):
        d = _decision()
        op = _operation_for(d, desired_marker="unexpected")
        d, _, token, patch = _artifacts(d, op)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, patch, d)

    def test_profile_rule_and_rule_aspect_mismatches_fail(self):
        for mutate in (
            lambda d: replace(d, rule_ref=replace(d.rule_ref, profile_version="4")),
            lambda d: replace(d, rule_ref=replace(d.rule_ref, aspect_id="P2")),
        ):
            bad = mutate(_decision())
            op = _operation_for(bad)
            bad, _, token, patch = _artifacts(bad, op)
            with self.assertRaises(TransformLogIntegrityError):
                build_transform_record(token, patch, bad)

    def test_missing_rule_ref_fails(self):
        d = replace(_decision(), rule_ref=None)
        op = _operation_for(d)
        d, _, token, patch = _artifacts(d, op)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, patch, d)

    def test_non_deterministic_change_fails(self):
        d = replace(_decision(), actionability=Actionability.NO_ACTION, desired_value=None)
        base = _decision()
        op = replace(_operation_for(base), decision_ref=_sha(serialize_decision(d)))
        d, _, token, patch = _artifacts(d, op)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, patch, d)

    def test_record_excludes_execution_artifacts_bytes_and_full_decision(self):
        d, _, token, patch = _artifacts()
        r = build_transform_record(token, patch, d)
        names = {f.name for f in fields(r)}
        self.assertTrue({"output_package_bytes", "cleared_operation", "patch_result", "source_decision"}.isdisjoint(names))
        self.assertFalse(any(isinstance(getattr(r, f.name), bytes) for f in fields(r)))

    def test_structural_path_is_stable_recorded_location(self):
        d, op, token, patch = _artifacts()
        self.assertEqual(build_transform_record(token, patch, d).target.structural_path,
                         op.target.structural_path)

    def test_builder_performs_no_file_io(self):
        d, _, token, patch = _artifacts()
        with mock_patch("builtins.open", side_effect=AssertionError("unexpected file IO")):
            r = build_transform_record(token, patch, d)
        self.assertEqual(r.operation_ref, token.operation_ref)

    def test_font_size_decision_decimal_binds_to_operation_lengthvalue(self):
        d = _decision(observed=Decimal("11"), desired=Decimal("12"), slot="font_size")
        d, op, token, patch = _artifacts(d)
        r = build_transform_record(token, patch, d)
        self.assertEqual(op.precondition_observed, LengthValue(Decimal("11"), "pt"))
        self.assertEqual(op.desired_value, LengthValue(Decimal("12"), "pt"))
        self.assertEqual(r.precondition_observed, op.precondition_observed)
        self.assertEqual(r.desired_value, op.desired_value)


class TransformLogSerializationTests(unittest.TestCase):
    def test_bool_json_and_reporting_provenance(self):
        d, _, token, patch = _artifacts()
        obj = json.loads(serialize_transform_record(build_transform_record(token, patch, d)))
        self.assertIs(obj["precondition_observed"], False)
        self.assertIs(obj["desired_value"], True)
        self.assertEqual(obj["profile_ref"]["profile_id"], "journal-x")
        self.assertEqual(obj["rule_ref"]["rule_id"], "body-bold")
        self.assertEqual(obj["target"]["target_class"], "body")
        self.assertEqual(obj["target"]["aspect_id"], "P1")
        self.assertEqual(obj["target"]["property_slot"], "bold")

    def test_length_decimal_serialization(self):
        d = _decision(observed=Decimal("11"), desired=Decimal("12"), slot="font_size")
        d, _, token, patch = _artifacts(d)
        obj = json.loads(serialize_transform_record(build_transform_record(token, patch, d)))
        self.assertEqual(obj["precondition_observed"], {"unit": "pt", "value": "11"})
        self.assertEqual(obj["desired_value"], {"unit": "pt", "value": "12"})

    def test_transform_ref_is_sha256(self):
        d, _, token, patch = _artifacts()
        r = build_transform_record(token, patch, d)
        data = serialize_transform_record(r)
        self.assertEqual(transform_ref(r), hashlib.sha256(data).hexdigest())

    def test_same_inputs_repeat_identically(self):
        d, _, token, patch = _artifacts()
        r1 = build_transform_record(token, patch, d)
        r2 = build_transform_record(token, patch, d)
        self.assertEqual(serialize_transform_record(r1), serialize_transform_record(r2))
        self.assertEqual(transform_ref(r1), transform_ref(r2))

    def test_no_timestamp_uuid_or_environment_fields(self):
        d, _, token, patch = _artifacts()
        obj = json.loads(serialize_transform_record(build_transform_record(token, patch, d)))
        forbidden = {"timestamp", "created_at", "duration", "uuid", "hostname", "machine", "environment"}
        self.assertTrue(forbidden.isdisjoint(obj))

    def test_serialization_is_valid_utf8_json(self):
        d, _, token, patch = _artifacts()
        data = serialize_transform_record(build_transform_record(token, patch, d))
        self.assertEqual(json.loads(data.decode("utf-8"))["decision_ref"], token.operation.decision_ref)


if __name__ == "__main__":
    unittest.main()
