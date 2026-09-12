"""OperationPlan v0.1 — E2E tests.

Proves the full pipeline without any manual TargetClassification:

    DOCX -> Parser -> Analysis -> Classification -> Decision -> OperationPlan

Frozen scenario (briefing item 55): body paragraph with bold=true, 11pt,
spacing 1.5, alignment both against a profile requiring bold=false, 12pt,
spacing 1.5, alignment both. Expected: 2 planned SET_PROPERTY operations
(bold, font_size) and 2 skipped results (spacing, alignment).
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from formatador_academico.analysis.formatting import (
    resolve_paragraph_formatting,
    resolve_run_formatting,
)
from formatador_academico.analysis.formatting_model import ANALYSIS_FORMATTING_VERSION
from formatador_academico.analysis.style_catalog import build_style_catalog
from formatador_academico.classification import (
    CLASSIFICATION_VERSION,
    classify_document,
    project_run_classification,
    project_target_classification,
)
from formatador_academico.decision import (
    DECISION_VERSION,
    DECISION_VOCABULARY_VERSION,
    DecisionContext,
    DecisionKey,
    FormattingRule,
    LineSpacingValue,
    ProfileRef,
    RuleMode,
    evaluate_target,
    extract_resolved_value,
)
from formatador_academico.docx_parser import DocxParser
from formatador_academico.operation_plan import (
    LengthValue,
    OperationKind,
    PlanningStatus,
    UpstreamVersions,
    build_operation_plan,
    serialize_operation_plan,
    source_document_ref_from_physical_ir,
)

from test_analysis_formatting_v01b_m1 import (
    build_docx,
    document,
    first_run,
    styles_part,
)
from test_classification_v01_e2e import NORMAL


def _build_e2e_plan():
    body = (
        '<w:p><w:pPr><w:jc w:val="both"/>'
        '<w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
        '<w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr>'
        "<w:t>corpo</w:t></w:r></w:p>"
    )
    pkg = build_docx(document(body), styles_part(NORMAL))
    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    catalog = build_style_catalog(pkg, ir)

    (paragraph_result,) = classify_document(ir, catalog)
    paragraph = ir["stories"][0]["blocks"][0]
    run = first_run(paragraph)
    run_result = project_run_classification(run, paragraph_result)

    pf = resolve_paragraph_formatting(paragraph, catalog, "word/document.xml")
    rf = resolve_run_formatting(run, paragraph, catalog, "word/document.xml")

    profile = ProfileRef("perfil-e2e", "1")
    run_classification = project_target_classification(run_result)
    paragraph_classification = project_target_classification(paragraph_result)

    contexts = {
        "bold": DecisionContext(
            DecisionKey("run", "P1", "bold"), run_classification, profile),
        "font": DecisionContext(
            DecisionKey("run", "P2", "font_size"), run_classification, profile),
        "spacing": DecisionContext(
            DecisionKey("paragraph", "P3", "spacing.line"),
            paragraph_classification, profile),
        "align": DecisionContext(
            DecisionKey("paragraph", "P4", "alignment"),
            paragraph_classification, profile),
    }
    rules = {
        "bold": FormattingRule("p1-bold", "P1", "bold", RuleMode.EXACT, expected=False),
        "font": FormattingRule("p2-size", "P2", "font_size", RuleMode.EXACT,
                               expected=Decimal("12")),
        "spacing": FormattingRule("p3-line", "P3", "spacing.line", RuleMode.EXACT,
                                  expected=LineSpacingValue("auto", Decimal("1.5"), "multiple")),
        "align": FormattingRule("p4-jc", "P4", "alignment", RuleMode.EXACT,
                                expected="both"),
    }
    analyses = {"bold": rf, "font": rf, "spacing": pf, "align": pf}

    decisions = ()
    for name in ("bold", "font", "spacing", "align"):
        ctx = contexts[name]
        (decision,) = evaluate_target((
            (rules[name], extract_resolved_value(ctx.key, analyses[name]), ctx),
        ))
        decisions += (decision,)

    source_document = source_document_ref_from_physical_ir(ir)
    upstream = UpstreamVersions(
        analysis_formatting_version=ANALYSIS_FORMATTING_VERSION,
        classification_version=CLASSIFICATION_VERSION,
        decision_version=DECISION_VERSION,
        decision_vocabulary_version=DECISION_VOCABULARY_VERSION,
    )
    plan = build_operation_plan(source_document, upstream, decisions)
    return ir, decisions, plan


class OperationPlanV01E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir, cls.decisions, cls.plan = _build_e2e_plan()

    # item 55/60.23 — full pipeline, exactly 2 operations (mutation budget)
    def test_two_operations_no_implicit_mutation(self):
        self.assertEqual(len(self.plan.operations), 2)
        self.assertEqual(len(self.plan.planning_results), 4)

    # item 56 — bold operation
    def test_bold_operation(self):
        (op,) = [o for o in self.plan.operations if o.key.property_slot == "bold"]
        self.assertEqual(op.kind, OperationKind.SET_PROPERTY)
        self.assertEqual((op.key.target_type, op.key.aspect_id), ("run", "P1"))
        self.assertIs(op.precondition_observed, True)
        self.assertIs(op.desired_value, False)
        bold_decision = self.decisions[0]
        self.assertEqual(op.target.structural_path, bold_decision.target.structural_path)
        self.assertEqual(op.target.physical_hash, bold_decision.target.physical_hash)
        self.assertEqual(op.target.target_class, bold_decision.target.target_class)

    # item 57 — font operation typed in pt, not half-points
    def test_font_operation(self):
        (op,) = [o for o in self.plan.operations if o.key.property_slot == "font_size"]
        self.assertEqual(op.kind, OperationKind.SET_PROPERTY)
        self.assertEqual(op.precondition_observed, LengthValue(Decimal("11"), "pt"))
        self.assertEqual(op.desired_value, LengthValue(Decimal("12"), "pt"))

    # item 58 — spacing and alignment skipped without operations
    def test_spacing_and_alignment_skipped(self):
        by_slot = {r.operation.key.property_slot if r.operation else None: r
                   for r in self.plan.planning_results}
        skipped = [r for r in self.plan.planning_results
                   if r.status is PlanningStatus.SKIPPED]
        self.assertEqual(len(skipped), 2)
        self.assertTrue(all(r.operation is None for r in skipped))
        skipped_actionabilities = {r.decision_actionability for r in skipped}
        self.assertEqual(skipped_actionabilities, {"no_action"})
        self.assertNotIn("spacing.line", by_slot)
        self.assertNotIn("alignment", by_slot)

    # item 59/47 — source document fingerprint from the real parsed DOCX
    def test_source_document_fingerprint_real(self):
        self.assertEqual(self.plan.source_document.package_sha256,
                         self.ir["package"]["sha256"])
        self.assertEqual(self.plan.source_document.parser_version,
                         self.ir["parser_version"])
        self.assertEqual(self.plan.planned_story_part, "word/document.xml")

    def test_envelope_serialization_stable(self):
        self.assertEqual(serialize_operation_plan(self.plan),
                         serialize_operation_plan(self.plan))

    def test_decision_ref_matches_canonical_decision(self):
        import hashlib
        from formatador_academico.decision import serialize_decision
        refs = {op.decision_ref for op in self.plan.operations}
        expected = {
            hashlib.sha256(serialize_decision(d)).hexdigest()
            for d in self.decisions
            if d.actionability.value == "deterministic_change"
        }
        self.assertEqual(refs, expected)


if __name__ == "__main__":
    unittest.main()
