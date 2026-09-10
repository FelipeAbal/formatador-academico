"""Patcher v0.1 — E2E tests (decision 0028 §26, scenarios 48/49).

Full frozen pipeline, no manual TargetClassification:

    DOCX -> Parser -> Analysis -> Classification -> Decision
    -> OperationPlan -> SafetyGate -> Patcher

Bold E2E: body paragraph bold=true against a profile requiring bold=false;
after the patch the re-parsed Analysis observes bold=false and everything
else is preserved.

Font E2E: run at 11pt against a profile requiring 12pt; after the patch the
Analysis observes font_size=12pt.

Also covers the v0.1 orchestration model (decision 0028 §25): after the
first applied patch, the remaining operation is executed only after
re-running the whole pipeline/gate on the new snapshot.
"""

from __future__ import annotations

import hashlib
import unittest
from decimal import Decimal

from formatador_academico.analysis.formatting import (
    resolve_paragraph_formatting,
    resolve_run_formatting,
)
from formatador_academico.analysis.formatting_model import (
    ANALYSIS_FORMATTING_VERSION,
    ResolutionStatus,
)
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
    ProfileRef,
    RuleMode,
    evaluate_target,
    extract_resolved_value,
)
from formatador_academico.decision.serialization import serialize_decision
from formatador_academico.docx_parser import DocxParser
from formatador_academico.operation_plan import (
    UpstreamVersions,
    build_operation_plan,
    source_document_ref_from_physical_ir,
)
from formatador_academico.patcher import PatchStatus, apply_cleared_operation
from formatador_academico.patcher.xml_patch import PPR_CANONICAL_ORDER
from formatador_academico.safety_gate import ContextStatus, evaluate_operation_plan
from formatador_academico.transform_log import build_transform_record

from test_analysis_formatting_v01b_m1 import (
    build_docx,
    document,
    first_run,
    styles_part,
)
from test_classification_v01_e2e import NORMAL

PROFILE = ProfileRef("perfil-e2e", "1")

BOLD_BODY = (
    '<w:p><w:pPr><w:jc w:val="both"/>'
    '<w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
    '<w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr>'
    "<w:t>corpo</w:t></w:r></w:p>"
)


def _full_pipeline(pkg, rules):
    """Run Parser -> Analysis -> Classification -> Decision -> OperationPlan
    -> SafetyGate and return the bound decisions alongside cleared tokens."""

    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    catalog = build_style_catalog(pkg, ir)

    (paragraph_result,) = classify_document(ir, catalog)
    paragraph = ir["stories"][0]["blocks"][0]
    run = first_run(paragraph)
    run_result = project_run_classification(run, paragraph_result)

    pf = resolve_paragraph_formatting(paragraph, catalog, "word/document.xml")
    rf = resolve_run_formatting(run, paragraph, catalog, "word/document.xml")

    run_classification = project_target_classification(run_result)
    paragraph_classification = project_target_classification(paragraph_result)

    contexts = {
        "bold": DecisionContext(
            DecisionKey("run", "P1", "bold"), run_classification, PROFILE),
        "font": DecisionContext(
            DecisionKey("run", "P2", "font_size"), run_classification, PROFILE),
        "spacing": DecisionContext(
            DecisionKey("paragraph", "P3", "spacing.line"),
            paragraph_classification, PROFILE),
        "align": DecisionContext(
            DecisionKey("paragraph", "P4", "alignment"),
            paragraph_classification, PROFILE),
    }
    analyses = {"bold": rf, "font": rf, "spacing": pf, "align": pf}

    decisions = ()
    for name in ("bold", "font", "spacing", "align"):
        ctx = contexts[name]
        (decision,) = evaluate_target(((rules[name], extract_resolved_value(ctx.key, analyses[name]), ctx),))
        decisions += (decision,)

    source_document = source_document_ref_from_physical_ir(ir)
    upstream = UpstreamVersions(
        analysis_formatting_version=ANALYSIS_FORMATTING_VERSION,
        classification_version=CLASSIFICATION_VERSION,
        decision_version=DECISION_VERSION,
        decision_vocabulary_version=DECISION_VOCABULARY_VERSION,
    )
    plan = build_operation_plan(source_document, upstream, decisions)
    report = evaluate_operation_plan(plan, decisions, ir, catalog, PROFILE)
    assert report.context_status is ContextStatus.COMPATIBLE
    tokens = {t.operation.key.property_slot: t for t in report.cleared_operations}
    return ir, catalog, tokens, decisions


def _rules(bold=False, size=Decimal("12")):
    from formatador_academico.decision import LineSpacingValue

    return {
        "bold": FormattingRule("p1-bold", "P1", "bold", RuleMode.EXACT, expected=bold),
        "font": FormattingRule("p2-size", "P2", "font_size", RuleMode.EXACT, expected=size),
        "spacing": FormattingRule("p3-line", "P3", "spacing.line", RuleMode.EXACT,
                                  expected=LineSpacingValue("auto", Decimal("1.5"), "multiple")),
        "align": FormattingRule("p4-jc", "P4", "alignment", RuleMode.EXACT, expected="both"),
    }


def _analysis(pkg, slot):
    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    catalog = build_style_catalog(pkg, ir)
    paragraph = ir["stories"][0]["blocks"][0]
    run = first_run(paragraph)
    rf = resolve_run_formatting(run, paragraph, catalog, "word/document.xml")
    return rf.bold if slot == "bold" else rf.font_size


def _decision_for_token(decisions, token):
    for decision in decisions:
        ref = hashlib.sha256(serialize_decision(decision)).hexdigest()
        if ref == token.operation.decision_ref:
            return decision
    raise AssertionError("no source Decision matches token.operation.decision_ref")


class PatcherV01E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg = build_docx(document(BOLD_BODY), styles_part(NORMAL))

    # scenario 48
    def test_e2e_bold(self):
        _, _, tokens, _ = _full_pipeline(self.pkg, _rules())
        self.assertIn("bold", tokens)
        self.assertIn("font_size", tokens)
        result = apply_cleared_operation(self.pkg, tokens["bold"])
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertEqual(result.changed_part, "word/document.xml")
        resolved = _analysis(result.output_package_bytes, "bold")
        self.assertEqual(resolved.status, ResolutionStatus.RESOLVED)
        self.assertIs(resolved.value, False)
        size = _analysis(result.output_package_bytes, "font_size")
        self.assertEqual(size.value.value, Decimal("11"))

    def test_e2e_alignment(self):
        body = (
            '<w:p><w:pPr><w:jc w:val="left"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="24"/></w:rPr>'
            '<w:t>alinhamento</w:t></w:r></w:p>'
        )
        pkg = build_docx(document(body), styles_part(NORMAL))
        _, _, tokens, _ = _full_pipeline(pkg, _rules())
        self.assertIn("alignment", tokens)
        result = apply_cleared_operation(pkg, tokens["alignment"])
        self.assertEqual(result.status, PatchStatus.APPLIED)
        ir = DocxParser().parse_bytes(result.output_package_bytes)
        catalog = build_style_catalog(result.output_package_bytes, ir)
        paragraph = ir["stories"][0]["blocks"][0]
        resolved = resolve_paragraph_formatting(paragraph, catalog, "word/document.xml")
        self.assertEqual(resolved.alignment.status, ResolutionStatus.RESOLVED)
        self.assertEqual(resolved.alignment.value, "both")

    # scenario 49
    def test_e2e_font_size(self):
        _, _, tokens, _ = _full_pipeline(self.pkg, _rules())
        result = apply_cleared_operation(self.pkg, tokens["font_size"])
        self.assertEqual(result.status, PatchStatus.APPLIED)
        resolved = _analysis(result.output_package_bytes, "font_size")
        self.assertEqual(resolved.status, ResolutionStatus.RESOLVED)
        self.assertEqual(resolved.value.value, Decimal("12"))
        self.assertEqual(resolved.value.unit, "pt")

    # decision 0030 §22 scenario 36: same structural_path survives the real
    # property-only patch and the record binds profile/rule + package lineage.
    def test_e2e_transform_record_after_real_patch(self):
        _, _, tokens, decisions = _full_pipeline(self.pkg, _rules())
        token = tokens["bold"]
        source_decision = _decision_for_token(decisions, token)
        result = apply_cleared_operation(self.pkg, token)
        self.assertEqual(result.status, PatchStatus.APPLIED)
        record = build_transform_record(token, result, source_decision)
        self.assertEqual(record.target.structural_path, token.operation.target.structural_path)
        self.assertEqual(record.input_package_sha256, token.current_package_sha256)
        self.assertEqual(record.output_package_sha256, result.output_package_sha256)
        self.assertEqual(record.profile_ref, source_decision.profile_ref)
        self.assertEqual(record.rule_ref, source_decision.rule_ref)
        # Output pipeline can still resolve the same physical path by contract.
        ir_out = DocxParser().parse_bytes(result.output_package_bytes)
        run_out = first_run(ir_out["stories"][0]["blocks"][0])
        self.assertEqual(run_out["structural_path"], record.target.structural_path)

    def test_sequential_mutations_via_pipeline_rerun(self):
        _, _, tokens, _ = _full_pipeline(self.pkg, _rules())
        first = apply_cleared_operation(self.pkg, tokens["bold"])
        self.assertEqual(first.status, PatchStatus.APPLIED)
        stale = apply_cleared_operation(first.output_package_bytes, tokens["font_size"])
        self.assertEqual(stale.status, PatchStatus.REJECTED)
        _, _, tokens2, _ = _full_pipeline(first.output_package_bytes, _rules())
        self.assertNotIn("bold", tokens2)
        second = apply_cleared_operation(first.output_package_bytes, tokens2["font_size"])
        self.assertEqual(second.status, PatchStatus.APPLIED)
        self.assertIs(_analysis(second.output_package_bytes, "bold").value, False)
        self.assertEqual(_analysis(second.output_package_bytes, "font_size").value.value, Decimal("12"))


class PatcherCanonicalParagraphOrderTests(unittest.TestCase):
    def test_ppr_order_uses_the_xsd_mirror_indents_local_name(self):
        self.assertIn("mirrorIndents", PPR_CANONICAL_ORDER)
        self.assertNotIn("mirrorInd", PPR_CANONICAL_ORDER)
        self.assertLess(
            PPR_CANONICAL_ORDER.index("mirrorIndents"),
            PPR_CANONICAL_ORDER.index("suppressOverlap"),
        )


if __name__ == "__main__":
    unittest.main()
