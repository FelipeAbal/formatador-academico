"""Adversarial/audit tests for Processing Report v0.1."""
from __future__ import annotations

import inspect
import os
import subprocess
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch as mock_patch

import formatador_academico.processing_report.builder as report_builder_module
import formatador_academico.processing_report.serialization as report_serialization_module
from formatador_academico.decision import Actionability, FormattingRule, RuleMode
from formatador_academico.processing_report import build_processing_report, processing_report_ref
from formatador_academico.processing_session import (
    ProcessingSessionStatus,
    RuleBinding,
    SessionFindingKind,
    process_document,
)
from formatador_academico.safety_gate import (
    ContextStatus,
    GateReason,
    GateResult,
    GateStatus,
    SafetyGateReport,
    evaluate_operation_plan as real_evaluate_operation_plan,
)

from test_processing_session_v01 import (
    _body_profile,
    _bold_rule,
    _paragraph,
    _pkg,
    _profile,
    _run,
    _two_change_pkg,
)


class ProcessingReportUnappliedTests(unittest.TestCase):
    def test_gate_blocked_becomes_unapplied_item(self):
        pkg = _pkg(_paragraph(_run("blocked", bold=True, half_points=24)))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))

        def block_gate(plan, decisions, ir, catalog, profile_ref):
            real = real_evaluate_operation_plan(plan, decisions, ir, catalog, profile_ref)
            reason = GateReason.PROFILE_CONTEXT_CHANGED
            blocked = tuple(
                GateResult(r.operation_ref, GateStatus.BLOCKED, (reason,), None)
                for r in real.results
            )
            return SafetyGateReport(
                real.safety_gate_version,
                real.operation_plan_ref,
                real.current_package_sha256,
                ContextStatus.BLOCKED,
                (reason,),
                blocked,
                (),
            )

        with mock_patch(
            "formatador_academico.processing_session.engine.evaluate_operation_plan",
            side_effect=block_gate,
        ):
            session = process_document(pkg, profile)
        report = build_processing_report(session)
        self.assertEqual(len(report.unapplied_changes), 1)
        item = report.unapplied_changes[0]
        self.assertEqual(item.finding_kind, SessionFindingKind.GATE_BLOCKED)
        self.assertEqual(item.reason, GateReason.PROFILE_CONTEXT_CHANGED.value)
        self.assertEqual(item.desired_value, False)

    def test_real_duplicate_property_patch_rejection_becomes_unapplied_item(self):
        run = (
            '<w:r><w:rPr><w:b/><w:b/><w:sz w:val="24"/></w:rPr>'
            '<w:t>duplicate</w:t></w:r>'
        )
        pkg = _pkg(_paragraph(run))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        session = process_document(pkg, profile)
        self.assertEqual(session.status, ProcessingSessionStatus.QUIESCENT_WITH_UNAPPLIED)
        self.assertEqual(len(session.findings), 1)
        self.assertEqual(session.findings[0].kind, SessionFindingKind.PATCH_REJECTED)
        report = build_processing_report(session)
        self.assertEqual(len(report.unapplied_changes), 1)
        self.assertEqual(
            report.unapplied_changes[0].finding_kind,
            SessionFindingKind.PATCH_REJECTED,
        )

    def test_operation_limit_becomes_unapplied_item(self):
        session = process_document(
            _two_change_pkg(), _body_profile(), max_applied_operations=1
        )
        self.assertEqual(session.status, ProcessingSessionStatus.OPERATION_LIMIT_REACHED)
        report = build_processing_report(session)
        self.assertEqual(report.summary.applied_change_count, 1)
        self.assertEqual(len(report.unapplied_changes), 1)
        self.assertEqual(
            report.unapplied_changes[0].finding_kind,
            SessionFindingKind.OPERATION_LIMIT,
        )

    def test_preserve_decision_is_not_review_item(self):
        rule = FormattingRule(
            "contain",
            "P1",
            "bold",
            RuleMode.CONTAINMENT,
        )
        pkg = _pkg(_paragraph(_run("preserve", bold=True, half_points=24)))
        session = process_document(pkg, _profile(RuleBinding("body", "run", rule)))
        self.assertTrue(
            any(d.actionability is Actionability.PRESERVE for d in session.final_decisions)
        )
        report = build_processing_report(session)
        self.assertEqual(report.review_items, ())


class ProcessingReportDeterminismAuditTests(unittest.TestCase):
    def test_runtime_has_no_docx_io_network_clock_random_or_dynamic_import(self):
        source = inspect.getsource(report_builder_module) + inspect.getsource(report_serialization_module)
        forbidden = (
            "open(",
            "zipfile",
            "lxml",
            "docx_parser",
            "requests",
            "socket",
            "datetime",
            "time.time",
            "random",
            "__import__",
        )
        for token in forbidden:
            self.assertNotIn(token, source, token)

    def test_cross_hashseed_report_ref_determinism(self):
        code = r'''
import sys
sys.path.insert(0, "tests")
from formatador_academico.processing_report import build_processing_report, processing_report_ref
from formatador_academico.processing_session import process_document
from test_processing_session_v01 import _two_change_pkg, _body_profile
session = process_document(_two_change_pkg(), _body_profile())
print(processing_report_ref(build_processing_report(session)))
'''
        outputs = []
        for seed in ("1", "17", "101"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = "src"
            completed = subprocess.run(
                [sys.executable, "-c", code],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            outputs.append(completed.stdout.strip())
        self.assertEqual(len(set(outputs)), 1)
        self.assertEqual(len(outputs[0]), 64)


if __name__ == "__main__":
    unittest.main()
