"""Classification Layer v0.1 — E2E tests.

Proves the new frozen-target pipeline

    DOCX -> Parser -> Analysis -> Classification -> Decision

without any hand-built TargetClassification, plus cross-process/hashseed
determinism of classification serialization.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from formatador_academico.analysis.formatting import (
    resolve_paragraph_formatting,
    resolve_run_formatting,
)
from formatador_academico.analysis.style_catalog import build_style_catalog
from formatador_academico.classification import (
    ClassificationStatus,
    TargetClass,
    classify_document,
    project_run_classification,
    project_target_classification,
)
from formatador_academico.decision import (
    Actionability,
    ComplianceStatus,
    DecisionContext,
    DecisionKey,
    FormattingRule,
    LineSpacingValue,
    ProfileRef,
    RuleMode,
    decide_property,
    evaluate_target,
    extract_resolved_value,
    serialize_target_decisions,
)
from formatador_academico.docx_parser import DocxParser

from test_analysis_formatting_v01b_m1 import (
    build_docx,
    document,
    first_run,
    styles_part,
)

NORMAL = (
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
    '<w:name w:val="Normal"/></w:style>'
)
HEADING1 = (
    '<w:style w:type="paragraph" w:styleId="Heading1">'
    '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/></w:style>'
)


class ClassificationV01E2EBody(unittest.TestCase):
    """Briefing item 44: body paragraph through the full pipeline."""

    def test_docx_to_decision_body_scenario_without_manual_target_class(self):
        # document: Normal body, bold=true, 11pt, alignment both, spacing 1.5
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
        self.assertEqual(paragraph_result.status, ClassificationStatus.CLASSIFIED)
        self.assertEqual(paragraph_result.target_class, TargetClass.BODY)

        paragraph = ir["stories"][0]["blocks"][0]
        run = first_run(paragraph)
        run_result = project_run_classification(run, paragraph_result)

        pf = resolve_paragraph_formatting(paragraph, catalog, "word/document.xml")
        rf = resolve_run_formatting(run, paragraph, catalog, "word/document.xml")
        self.assertEqual(pf.paragraph_path, paragraph_result.structural_path)
        self.assertEqual(rf.run_path, run_result.structural_path)

        # TargetClassification now comes from the Classification Layer only.
        profile = ProfileRef("perfil-e2e", "1")
        run_classification = project_target_classification(run_result)
        paragraph_classification = project_target_classification(paragraph_result)
        self.assertEqual(run_classification.provenance,
                         "classification:inherited_from_paragraph")
        self.assertEqual(paragraph_classification.provenance, "classification:direct")

        run_ctx_bold = DecisionContext(
            DecisionKey("run", "P1", "bold"), run_classification, profile)
        run_ctx_font = DecisionContext(
            DecisionKey("run", "P2", "font_size"), run_classification, profile)
        spacing_ctx = DecisionContext(
            DecisionKey("paragraph", "P3", "spacing.line"),
            paragraph_classification, profile)
        align_ctx = DecisionContext(
            DecisionKey("paragraph", "P4", "alignment"),
            paragraph_classification, profile)

        bold_rule = FormattingRule("p1-bold", "P1", "bold", RuleMode.EXACT, expected=False)
        font_rule = FormattingRule("p2-size", "P2", "font_size", RuleMode.EXACT,
                                   expected=Decimal("12"))
        spacing_rule = FormattingRule("p3-line", "P3", "spacing.line", RuleMode.EXACT,
                                      expected=LineSpacingValue("auto", Decimal("1.5"), "multiple"))
        align_rule = FormattingRule("p4-jc", "P4", "alignment", RuleMode.EXACT,
                                    expected="both")

        run_decisions = evaluate_target((
            (bold_rule, extract_resolved_value(run_ctx_bold.key, rf), run_ctx_bold),
            (font_rule, extract_resolved_value(run_ctx_font.key, rf), run_ctx_font),
        ))
        para_decisions = evaluate_target((
            (spacing_rule, extract_resolved_value(spacing_ctx.key, pf), spacing_ctx),
            (align_rule, extract_resolved_value(align_ctx.key, pf), align_ctx),
        ))

        bold_d, font_d = run_decisions
        spacing_d, align_d = para_decisions
        # same expectations as the frozen manual-classification E2E (0021)
        self.assertEqual(bold_d.compliance, ComplianceStatus.NON_COMPLIANT)
        self.assertEqual(bold_d.actionability, Actionability.DETERMINISTIC_CHANGE)
        self.assertIs(bold_d.desired_value, False)
        self.assertEqual(font_d.compliance, ComplianceStatus.NON_COMPLIANT)
        self.assertEqual(font_d.actionability, Actionability.DETERMINISTIC_CHANGE)
        self.assertEqual(font_d.desired_value, Decimal("12"))
        self.assertEqual(spacing_d.compliance, ComplianceStatus.COMPLIANT)
        self.assertEqual(spacing_d.actionability, Actionability.NO_ACTION)
        self.assertEqual(align_d.compliance, ComplianceStatus.COMPLIANT)
        self.assertEqual(align_d.actionability, Actionability.NO_ACTION)

        blob1 = serialize_target_decisions(run_decisions + para_decisions)
        blob2 = serialize_target_decisions(run_decisions + para_decisions)
        self.assertEqual(blob1, blob2)
        # classification provenance lives in the projected TargetClassification
        # (the frozen Decision envelope does not re-serialize it, per 0021)
        self.assertEqual(paragraph_classification.classification_version, "0.1")
        self.assertEqual(run_classification.classification_version, "0.1")
        self.assertIn(b'"decision_vocabulary_version":"0.1"', blob1)


class ClassificationV01E2EHeading(unittest.TestCase):
    """Briefing item 45: Heading1 classifies and projects correctly."""

    def test_docx_to_classification_heading_level_1(self):
        body = (
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>Introdução</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>corpo do texto</w:t></w:r></w:p>'
        )
        pkg = build_docx(document(body), styles_part(NORMAL + HEADING1))
        ir = DocxParser().parse_bytes(pkg)
        assert ir["status"] == "ok", ir.get("errors")
        catalog = build_style_catalog(pkg, ir)

        heading_result, body_result = classify_document(ir, catalog)
        self.assertEqual(heading_result.status, ClassificationStatus.CLASSIFIED)
        self.assertEqual(heading_result.target_class, TargetClass.HEADING)
        self.assertEqual(heading_result.metadata, (("level", 1),))
        self.assertEqual(heading_result.basis.value, "explicit")
        self.assertEqual(body_result.target_class, TargetClass.BODY)

        paragraph = ir["stories"][0]["blocks"][0]
        run = first_run(paragraph)
        run_result = project_run_classification(run, heading_result)
        self.assertEqual(run_result.target_class, TargetClass.HEADING)
        self.assertEqual(run_result.metadata, (("level", 1),))

        projected = project_target_classification(heading_result)
        self.assertEqual(
            (projected.target_type, projected.target_class, projected.provenance),
            ("paragraph", "heading", "classification:direct"),
        )
        projected_run = project_target_classification(run_result)
        self.assertEqual(
            (projected_run.target_type, projected_run.target_class,
             projected_run.provenance),
            ("run", "heading", "classification:inherited_from_paragraph"),
        )


class ClassificationV01Determinism(unittest.TestCase):
    def test_cross_process_hashseed_determinism(self):
        repo = Path(__file__).resolve().parents[1]
        code = r'''import sys
sys.path.insert(0, "tests")
from formatador_academico.docx_parser import DocxParser
from formatador_academico.analysis.style_catalog import build_style_catalog
from formatador_academico.classification import classify_document, serialize_classification_results
from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
styles = styles_part(
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/></w:style>')
body = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>t</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>corpo</w:t></w:r></w:p><w:p/>')
pkg = build_docx(document(body), styles)
ir = DocxParser().parse_bytes(pkg)
catalog = build_style_catalog(pkg, ir)
print(serialize_classification_results(classify_document(ir, catalog)).hex())'''
        outputs = []
        for seed in ("0", "42", "7"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = str(repo / "src")
            proc = subprocess.run([sys.executable, "-c", code], cwd=repo, env=env,
                                  capture_output=True, text=True, check=True)
            outputs.append(proc.stdout.strip())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])


if __name__ == "__main__":
    unittest.main()
