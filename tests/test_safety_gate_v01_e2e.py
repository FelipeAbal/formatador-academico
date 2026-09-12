"""SafetyGate v0.1 — E2E tests.

Proves the full frozen pipeline plus the gate, without any manual
TargetClassification:

    DOCX -> Parser -> Analysis -> Classification -> Decision
    -> OperationPlan -> SafetyGate

Frozen scenario: body paragraph with bold=true, 11pt, spacing 1.5,
alignment both, against a profile requiring bold=false, 12pt, spacing 1.5,
alignment both -> 2 planned SET_PROPERTY operations (bold, font_size);
spacing/alignment remain upstream skipped and are not gate operations.

E2E 1: unchanged document -> context compatible, exactly 2 cleared.
E2E 2: modified document re-parsed -> global veto source_document_changed,
       every operation blocked, no local checks executed.
"""

from __future__ import annotations

import unittest

from formatador_academico.analysis.style_catalog import build_style_catalog
from formatador_academico.decision import ProfileRef
from formatador_academico.docx_parser import DocxParser
from formatador_academico.safety_gate import (
    ContextStatus,
    GateReason,
    GateStatus,
    evaluate_operation_plan,
    serialize_safety_gate_report,
)

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL
from test_operation_plan_v01_e2e import _build_e2e_plan

BODY = (
    '<w:p><w:pPr><w:jc w:val="both"/>'
    '<w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
    '<w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr>'
    "<w:t>corpo</w:t></w:r></w:p>"
)


def _package(body=BODY):
    return build_docx(document(body), styles_part(NORMAL))


class SafetyGateV01E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir, cls.decisions, cls.plan = _build_e2e_plan()
        cls.pkg = _package()
        assert cls.ir["package"]["sha256"] == (
            DocxParser().parse_bytes(cls.pkg)["package"]["sha256"])
        cls.catalog = build_style_catalog(cls.pkg, cls.ir)
        cls.profile = ProfileRef("perfil-e2e", "1")

    def test_unchanged_document_two_cleared(self):
        report = evaluate_operation_plan(
            self.plan, self.decisions, self.ir, self.catalog, self.profile)
        self.assertEqual(report.context_status, ContextStatus.COMPATIBLE)
        self.assertEqual(report.context_reasons, ())
        self.assertEqual(len(report.results), 2)
        self.assertTrue(all(r.status is GateStatus.CLEARED for r in report.results))
        self.assertEqual(len(report.cleared_operations), 2)
        for token in report.cleared_operations:
            self.assertEqual(token.current_package_sha256,
                             self.ir["package"]["sha256"])

    def test_stale_package_global_block(self):
        pkg_b = _package(BODY.replace("corpo", "alterado"))
        ir_b = DocxParser().parse_bytes(pkg_b)
        assert ir_b["package"]["sha256"] != self.ir["package"]["sha256"]
        catalog_b = build_style_catalog(pkg_b, ir_b)
        report = evaluate_operation_plan(
            self.plan, self.decisions, ir_b, catalog_b, self.profile)
        self.assertEqual(report.context_status, ContextStatus.BLOCKED)
        self.assertEqual(report.context_reasons, (GateReason.SOURCE_DOCUMENT_CHANGED,))
        self.assertEqual(len(report.results), 2)
        self.assertTrue(all(r.status is GateStatus.BLOCKED for r in report.results))
        self.assertTrue(all(r.reasons == (GateReason.SOURCE_DOCUMENT_CHANGED,)
                            for r in report.results))
        self.assertEqual(report.cleared_operations, ())

    def test_report_serialization_stable(self):
        report = evaluate_operation_plan(
            self.plan, self.decisions, self.ir, self.catalog, self.profile)
        self.assertEqual(serialize_safety_gate_report(report),
                         serialize_safety_gate_report(report))


if __name__ == "__main__":
    unittest.main()
