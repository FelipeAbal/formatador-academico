"""Focused adversarial regressions for SafetyGate v0.1 audit fixes."""

from __future__ import annotations

import unittest

from formatador_academico.operation_plan import operation_ref
from formatador_academico.safety_gate import (
    ContextStatus,
    GateReason,
    GateResult,
    GateStatus,
    SafetyGateIntegrityError,
    SafetyGateReport,
)
from formatador_academico.safety_gate.model import (
    GateClearedOperation,
    _EMISSION_PROOF,
)

from test_safety_gate_v01 import PROFILE, _bold_font_plan, _evaluate, _parse


class TestAuditTokenSelfConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ir, cls.catalog, _, cls.run_rec = _parse()
        cls.decisions, cls.plan = _bold_font_plan(cls.ir, cls.run_rec)
        cls.report = _evaluate(cls.plan, cls.decisions, cls.ir, cls.catalog, PROFILE)
        cls.op_a, cls.op_b = cls.plan.operations

    def test_token_rejects_ref_from_other_operation(self):
        with self.assertRaises(SafetyGateIntegrityError):
            GateClearedOperation(
                operation=self.op_a,
                operation_ref=operation_ref(self.op_b),
                operation_plan_ref=self.report.operation_plan_ref,
                current_package_sha256=self.report.current_package_sha256,
                _proof=_EMISSION_PROOF,
            )

    def test_emitted_tokens_are_self_consistent(self):
        for token in self.report.cleared_operations:
            self.assertEqual(token.operation_ref, operation_ref(token.operation))


class TestAuditReportReasonConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ir, cls.catalog, _, cls.run_rec = _parse()
        cls.decisions, cls.plan = _bold_font_plan(cls.ir, cls.run_rec)
        cls.report = _evaluate(cls.plan, cls.decisions, cls.ir, cls.catalog, PROFILE)
        cls.ref = cls.report.results[0].operation_ref

    def _base_kwargs(self):
        return dict(
            safety_gate_version=self.report.safety_gate_version,
            operation_plan_ref=self.report.operation_plan_ref,
            current_package_sha256=self.report.current_package_sha256,
            cleared_operations=(),
        )

    def test_compatible_context_rejects_global_reason_result(self):
        result = GateResult(
            operation_ref=self.ref,
            status=GateStatus.BLOCKED,
            reasons=(GateReason.SOURCE_DOCUMENT_CHANGED,),
            evidence=None,
        )
        with self.assertRaises(ValueError):
            SafetyGateReport(
                context_status=ContextStatus.COMPATIBLE,
                context_reasons=(),
                results=(result,),
                **self._base_kwargs(),
            )

    def test_blocked_context_rejects_local_reason_result(self):
        result = GateResult(
            operation_ref=self.ref,
            status=GateStatus.BLOCKED,
            reasons=(GateReason.PRECONDITION_MISMATCH,),
            evidence=None,
        )
        with self.assertRaises(ValueError):
            SafetyGateReport(
                context_status=ContextStatus.BLOCKED,
                context_reasons=(GateReason.SOURCE_DOCUMENT_CHANGED,),
                results=(result,),
                **self._base_kwargs(),
            )

    def test_blocked_context_rejects_cleared_result(self):
        result = GateResult(
            operation_ref=self.ref,
            status=GateStatus.CLEARED,
            reasons=(),
            evidence=None,
        )
        with self.assertRaises(ValueError):
            SafetyGateReport(
                context_status=ContextStatus.BLOCKED,
                context_reasons=(GateReason.SOURCE_DOCUMENT_CHANGED,),
                results=(result,),
                **self._base_kwargs(),
            )

    def test_blocked_context_requires_single_canonical_reason(self):
        with self.assertRaises(ValueError):
            SafetyGateReport(
                context_status=ContextStatus.BLOCKED,
                context_reasons=(
                    GateReason.SOURCE_DOCUMENT_CHANGED,
                    GateReason.PARSER_VERSION_MISMATCH,
                ),
                results=(),
                **self._base_kwargs(),
            )


class TestAuditPublicSurface(unittest.TestCase):
    def test_safety_gate_report_is_publicly_exported(self):
        from formatador_academico import safety_gate

        self.assertIs(safety_gate.SafetyGateReport, SafetyGateReport)


if __name__ == "__main__":
    unittest.main()
