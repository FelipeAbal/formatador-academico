"""Adversarial public-model tests for Processing Session v0.1."""
from __future__ import annotations

import unittest
from dataclasses import replace

from formatador_academico.operation_plan import operation_ref
from formatador_academico.processing_session import (
    ProcessingSessionStatus,
    SessionFinding,
    SessionFindingKind,
    process_document,
)

from test_processing_session_v01 import _body_profile, _two_change_pkg


class ProcessingSessionFindingInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.limited = process_document(
            _two_change_pkg(), _body_profile(), max_applied_operations=1
        )
        cls.finding = cls.limited.findings[0]

    def test_finding_operation_ref_is_mandatory_sha(self):
        with self.assertRaises((TypeError, ValueError)):
            replace(self.finding, operation_ref=None)

    def test_gate_finding_rejects_non_gate_reason(self):
        with self.assertRaises(ValueError):
            SessionFinding(
                SessionFindingKind.GATE_BLOCKED,
                self.finding.decision_ref,
                self.finding.operation_ref,
                self.finding.target,
                "not_a_gate_reason",
            )

    def test_patch_finding_rejects_impossible_snapshot_reason(self):
        with self.assertRaises(ValueError):
            SessionFinding(
                SessionFindingKind.PATCH_REJECTED,
                self.finding.decision_ref,
                self.finding.operation_ref,
                self.finding.target,
                "snapshot_hash_mismatch",
            )

    def test_operation_limit_reason_is_exact(self):
        with self.assertRaises(ValueError):
            replace(self.finding, reason="something_else")


class ProcessingSessionResultInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.limited = process_document(
            _two_change_pkg(), _body_profile(), max_applied_operations=1
        )

    def test_finding_must_bind_final_decision_ref(self):
        bad = replace(self.limited.findings[0], decision_ref="f" * 64)
        with self.assertRaises(ValueError):
            replace(self.limited, findings=(bad,))

    def test_finding_target_must_match_final_decision_target(self):
        target = replace(self.limited.findings[0].target, target_class="heading")
        bad = replace(self.limited.findings[0], target=target)
        with self.assertRaises(ValueError):
            replace(self.limited, findings=(bad,))

    def test_quiescent_cannot_hide_deterministic_change(self):
        with self.assertRaises(ValueError):
            replace(
                self.limited,
                status=ProcessingSessionStatus.QUIESCENT,
                findings=(),
            )

    def test_quiescent_with_unapplied_requires_deterministic_final_decision(self):
        done = process_document(_two_change_pkg(), _body_profile())
        operation = self.limited.findings[0]
        # Fabricate an otherwise-shaped unresolved finding against a completed
        # result. It cannot bind to a remaining deterministic Decision.
        with self.assertRaises(ValueError):
            replace(
                done,
                status=ProcessingSessionStatus.QUIESCENT_WITH_UNAPPLIED,
                findings=(operation,),
            )

    def test_operation_limit_requires_remaining_deterministic_change(self):
        done = process_document(_two_change_pkg(), _body_profile())
        with self.assertRaises(ValueError):
            replace(
                done,
                status=ProcessingSessionStatus.OPERATION_LIMIT_REACHED,
                findings=(self.limited.findings[0],),
            )


if __name__ == "__main__":
    unittest.main()
