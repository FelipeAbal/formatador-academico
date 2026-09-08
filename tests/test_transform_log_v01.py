"""TransformLog v0.1 contract tests (decision 0030)."""
from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import fields, replace
from decimal import Decimal

from formatador_academico.decision.model import (
    Actionability,
    ComplianceStatus,
    Decision,
    DecisionReason,
    DecisionTarget,
    ProfileRef,
    RuleRef,
)
from formatador_academico.decision.serialization import serialize_decision
from formatador_academico.operation_plan.model import (
    LengthValue,
    OperationKind,
    OperationTarget,
    PlannedOperation,
)
from formatador_academico.operation_plan.serialization import operation_ref
from formatador_academico.patcher.model import PatchReason, PatchResult, PatchStatus
from formatador_academico.safety_gate.model import GateClearedOperation, _EMISSION_PROOF
from formatador_academico.transform_log import (
    TRANSFORM_LOG_VERSION,
    TransformLogContractError,
    TransformLogIntegrityError,
    build_transform_record,
    serialize_transform_record,
    transform_ref,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decision(*, observed=False, desired=True, target_class="body") -> Decision:
    profile = ProfileRef("journal-x", "3")
    rule = RuleRef("journal-x", "3", "body-bold", "P1", "body.bold")
    target = DecisionTarget(
        "run", "/w:document/w:body[1]/w:p[1]/w:r[1]", "a" * 64,
        target_class, "P1", "bold",
    )
    return Decision(
        decision_version="0.1",
        decision_vocabulary_version="0.1",
        target=target,
        compliance=ComplianceStatus.NON_COMPLIANT,
        actionability=Actionability.DETERMINISTIC_CHANGE,
        reason=DecisionReason.DIFFERS_FROM_RULE,
        analysis_status="resolved",
        observed=observed,
        desired_value=desired,
        profile_ref=profile,
        rule_ref=rule,
        evidence_ref=None,
        decision_warnings=(),
    )


def _artifacts(decision: Decision | None = None):
    decision = decision or _decision()
    decision_ref = _sha(serialize_decision(decision))
    dt = decision.target
    target = OperationTarget(
        dt.target_type, dt.structural_path, dt.physical_hash, dt.target_class,
        dt.aspect_id, dt.property_slot,
    )
    operation = PlannedOperation(
        kind=OperationKind.SET_PROPERTY,
        key=__import__("formatador_academico.decision.model", fromlist=["DecisionKey"]).DecisionKey(
            dt.target_type, dt.aspect_id, dt.property_slot
        ),
        target=target,
        precondition_observed=decision.observed,
        desired_value=decision.desired_value,
        decision_ref=decision_ref,
    )
    op_ref = operation_ref(operation)
    plan_ref = "b" * 64
    input_sha = "c" * 64
    token = GateClearedOperation(
        operation=operation,
        operation_ref=op_ref,
        operation_plan_ref=plan_ref,
        current_package_sha256=input_sha,
        _proof=_EMISSION_PROOF,
    )
    output = b"patched-docx-placeholder"
    patch = PatchResult(
        patcher_version="0.1",
        status=PatchStatus.APPLIED,
        operation_ref=op_ref,
        operation_plan_ref=plan_ref,
        input_package_sha256=input_sha,
        output_package_sha256=_sha(output),
        output_package_bytes=output,
        reason=None,
        changed_part="word/document.xml",
    )
    return decision, operation, token, patch


class TransformLogBuildTests(unittest.TestCase):
    def test_valid_applied_build(self):
        decision, operation, token, patch = _artifacts()
        record = build_transform_record(token, patch, decision)
        self.assertEqual(record.transform_log_version, TRANSFORM_LOG_VERSION)
        self.assertEqual(record.operation_ref, token.operation_ref)
        self.assertEqual(record.decision_ref, operation.decision_ref)
        self.assertEqual(record.profile_ref, decision.profile_ref)
        self.assertEqual(record.rule_ref, decision.rule_ref)
        self.assertEqual(record.target, operation.target)
        self.assertEqual(record.precondition_observed, operation.precondition_observed)
        self.assertEqual(record.desired_value, operation.desired_value)
        self.assertEqual(record.input_package_sha256, patch.input_package_sha256)
        self.assertEqual(record.output_package_sha256, patch.output_package_sha256)

    def test_rejected_patch_cannot_build(self):
        decision, _, token, patch = _artifacts()
        rejected = PatchResult(
            patcher_version="0.1", status=PatchStatus.REJECTED,
            operation_ref=patch.operation_ref, operation_plan_ref=patch.operation_plan_ref,
            input_package_sha256=patch.input_package_sha256,
            output_package_sha256=None, output_package_bytes=None,
            reason=PatchReason.UNSUPPORTED_OPERATION, changed_part=None,
        )
        with self.assertRaises(TransformLogContractError):
            build_transform_record(token, rejected, decision)

    def test_wrong_input_types_fail_contract(self):
        decision, operation, token, patch = _artifacts()
        with self.assertRaises(TransformLogContractError):
            build_transform_record(operation, patch, decision)
        with self.assertRaises(TransformLogContractError):
            build_transform_record(token, object(), decision)
        with self.assertRaises(TransformLogContractError):
            build_transform_record(token, patch, object())

    def test_patch_operation_ref_mismatch(self):
        decision, _, token, patch = _artifacts()
        bad = replace(patch, operation_ref="d" * 64)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, bad, decision)

    def test_patch_plan_ref_mismatch(self):
        decision, _, token, patch = _artifacts()
        bad = replace(patch, operation_plan_ref="d" * 64)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, bad, decision)

    def test_patch_input_sha_mismatch(self):
        decision, _, token, patch = _artifacts()
        bad = replace(patch, input_package_sha256="d" * 64)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, bad, decision)

    def test_wrong_source_decision_ref(self):
        decision, _, token, patch = _artifacts()
        other = _decision(target_class="heading")
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, patch, other)

    def test_source_decision_target_must_match_operation(self):
        decision = _decision()
        decision_ref = _sha(serialize_decision(decision))
        wrong_target = OperationTarget(
            "run", decision.target.structural_path, decision.target.physical_hash,
            "heading", "P1", "bold",
        )
        from formatador_academico.decision.model import DecisionKey
        operation = PlannedOperation(
            OperationKind.SET_PROPERTY, DecisionKey("run", "P1", "bold"), wrong_target,
            decision.observed, decision.desired_value, decision_ref,
        )
        token = GateClearedOperation(operation, operation_ref(operation), "b"*64, "c"*64, _EMISSION_PROOF)
        output = b"out"
        patch = PatchResult("0.1", PatchStatus.APPLIED, token.operation_ref, "b"*64, "c"*64,
                            _sha(output), output, None, "word/document.xml")
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(token, patch, decision)

    def test_profile_rule_mismatch_fails_integrity(self):
        decision, _, token, patch = _artifacts()
        bad_rule = replace(decision.rule_ref, profile_version="4")
        bad = replace(decision, rule_ref=bad_rule)
        bad_ref = _sha(serialize_decision(bad))
        op = replace(token.operation, decision_ref=bad_ref)
        forged = GateClearedOperation(op, operation_ref(op), token.operation_plan_ref,
                                      token.current_package_sha256, _EMISSION_PROOF)
        bad_patch = replace(patch, operation_ref=forged.operation_ref)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(forged, bad_patch, bad)

    def test_no_rule_ref_fails_integrity(self):
        decision, _, token, patch = _artifacts()
        bad = replace(decision, rule_ref=None)
        bad_ref = _sha(serialize_decision(bad))
        op = replace(token.operation, decision_ref=bad_ref)
        forged = GateClearedOperation(op, operation_ref(op), token.operation_plan_ref,
                                      token.current_package_sha256, _EMISSION_PROOF)
        bad_patch = replace(patch, operation_ref=forged.operation_ref)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(forged, bad_patch, bad)

    def test_non_deterministic_change_fails_integrity(self):
        decision, _, token, patch = _artifacts()
        # Decision model requires desired iff deterministic_change, so construct a valid
        # NO_ACTION Decision with no desired, then bind an operation to its ref.
        bad = replace(decision, actionability=Actionability.NO_ACTION, desired_value=None)
        bad_ref = _sha(serialize_decision(bad))
        op = replace(token.operation, decision_ref=bad_ref)
        forged = GateClearedOperation(op, operation_ref(op), token.operation_plan_ref,
                                      token.current_package_sha256, _EMISSION_PROOF)
        bad_patch = replace(patch, operation_ref=forged.operation_ref)
        with self.assertRaises(TransformLogIntegrityError):
            build_transform_record(forged, bad_patch, bad)

    def test_record_does_not_embed_execution_artifacts_or_bytes(self):
        decision, _, token, patch = _artifacts()
        record = build_transform_record(token, patch, decision)
        names = {f.name for f in fields(record)}
        self.assertNotIn("output_package_bytes", names)
        self.assertNotIn("cleared_operation", names)
        self.assertNotIn("patch_result", names)
        self.assertFalse(any(isinstance(getattr(record, f.name), bytes) for f in fields(record)))

    def test_structural_path_is_reused_as_stable_location(self):
        decision, operation, token, patch = _artifacts()
        record = build_transform_record(token, patch, decision)
        self.assertEqual(record.target.structural_path, operation.target.structural_path)


class TransformLogSerializationTests(unittest.TestCase):
    def test_bool_serialization_is_canonical_and_roundtrippable(self):
        decision, _, token, patch = _artifacts()
        record = build_transform_record(token, patch, decision)
        data = serialize_transform_record(record)
        obj = json.loads(data)
        self.assertIs(obj["precondition_observed"], False)
        self.assertIs(obj["desired_value"], True)
        self.assertEqual(obj["profile_ref"]["profile_id"], "journal-x")
        self.assertEqual(obj["rule_ref"]["rule_id"], "body-bold")

    def test_length_decimal_serialization(self):
        decision = _decision(observed=LengthValue(Decimal("11")), desired=LengthValue(Decimal("12")))
        # align target/rule/key to font_size
        decision = replace(
            decision,
            target=replace(decision.target, aspect_id="P2", property_slot="font_size"),
            rule_ref=replace(decision.rule_ref, rule_id="body-font", aspect_id="P2", path="body.font_size"),
        )
        decision, _, token, patch = _artifacts(decision)
        record = build_transform_record(token, patch, decision)
        obj = json.loads(serialize_transform_record(record))
        self.assertEqual(obj["precondition_observed"], {"unit": "pt", "value": "11"})
        self.assertEqual(obj["desired_value"], {"unit": "pt", "value": "12"})

    def test_transform_ref_is_sha256_of_serialized_bytes(self):
        decision, _, token, patch = _artifacts()
        record = build_transform_record(token, patch, decision)
        data = serialize_transform_record(record)
        self.assertEqual(transform_ref(record), hashlib.sha256(data).hexdigest())

    def test_same_inputs_repeat_identically(self):
        decision, _, token, patch = _artifacts()
        r1 = build_transform_record(token, patch, decision)
        r2 = build_transform_record(token, patch, decision)
        self.assertEqual(serialize_transform_record(r1), serialize_transform_record(r2))
        self.assertEqual(transform_ref(r1), transform_ref(r2))

    def test_serialized_shape_has_no_timestamp_uuid_or_environment(self):
        decision, _, token, patch = _artifacts()
        obj = json.loads(serialize_transform_record(build_transform_record(token, patch, decision)))
        forbidden = {"timestamp", "created_at", "duration", "uuid", "hostname", "machine", "environment"}
        self.assertTrue(forbidden.isdisjoint(obj))

    def test_serialized_shape_contains_reporting_provenance(self):
        decision, _, token, patch = _artifacts()
        obj = json.loads(serialize_transform_record(build_transform_record(token, patch, decision)))
        self.assertEqual(obj["target"]["target_class"], "body")
        self.assertEqual(obj["target"]["aspect_id"], "P1")
        self.assertEqual(obj["target"]["property_slot"], "bold")
        self.assertEqual(obj["changed_part"], "word/document.xml")
        self.assertEqual(obj["patcher_version"], "0.1")
        self.assertEqual(obj["transform_log_version"], "0.1")


if __name__ == "__main__":
    unittest.main()
