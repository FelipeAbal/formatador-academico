"""Human-readable Processing Report v0.1 tests (decision 0045)."""
from __future__ import annotations

import ast
import hashlib
import json
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from formatador_academico.decision import DecisionWarning
from formatador_academico.human_report import (
    HUMAN_REPORT_MEDIA_TYPE,
    HUMAN_REPORT_VERSION,
    HumanReportContractError,
    HumanReportIntegrityError,
    RenderedProcessingReport,
    render_processing_report,
)
from formatador_academico.operation_plan import LengthValue
from formatador_academico.processing_report import processing_report_ref
from formatador_academico.product_input_boundary import build_product_from_inputs

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL


def _json(rules):
    return json.dumps(
        {
            "schema_version": "0.1",
            "profile": {"id": "human-report", "version": "1"},
            "rules": rules,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _bold(value=False):
    return {"body": {"bold": {"mode": "exact", "value": value}}}


def _font(value=12):
    return {"body": {"font_size": {"mode": "exact", "value": value}}}

def _line_spacing(value=1.5, schema="0.3"):
    return json.dumps(
        {
            "schema_version": schema,
            "profile": {"id": "human-report-p3", "version": "1"},
            "rules": {"body": {"line_spacing": {"mode": "exact", "value": value}}},
        },
        separators=(",", ":"),
    ).encode("utf-8")




def _run(text, *, bold_xml='<w:b w:val="0"/>', half_points=24):
    return (
        "<w:r><w:rPr>"
        + bold_xml
        + f'<w:sz w:val="{half_points}"/>'
        + f"</w:rPr><w:t>{text}</w:t></w:r>"
    )


def _paragraph(*runs, style=True):
    ppr = '<w:pPr><w:pStyle w:val="Normal"/></w:pPr>' if style else ""
    return "<w:p>" + ppr + "".join(runs) + "</w:p>"


def _pkg(body, styles=NORMAL):
    return build_docx(document(body), styles_part(styles))


def _report(pkg, rules):
    return build_product_from_inputs(pkg, _json(rules)).processing_report


def _text(rendered):
    return rendered.content_bytes.decode("utf-8")


class HumanReportRealFlowTests(unittest.TestCase):
    def test_no_change_renders_all_sections_and_counts(self):
        report = _report(_pkg(_paragraph(_run("ok"))), _bold(False))
        rendered = render_processing_report(report)
        text = _text(rendered)
        self.assertIn("# Relatório de processamento", text)
        for heading in (
            "## Resumo",
            "## Alterações aplicadas",
            "## Alterações não aplicadas",
            "## Itens para revisão",
            "## Observações de classificação",
            "## Limitações e interpretação",
        ):
            self.assertIn(heading, text)
        self.assertIn("- Alterações aplicadas: 0", text)
        self.assertIn("- Itens para revisão: 0", text)
        self.assertGreaterEqual(text.count("Nenhum item."), 4)
        self.assertIn("não significa conformidade integral", text)

    def test_applied_bold_real(self):
        report = _report(_pkg(_paragraph(_run("bold", bold_xml="<w:b/>"))), _bold(False))
        text = _text(render_processing_report(report))
        self.assertIn("Negrito", text)
        self.assertIn("- Antes: sim", text)
        self.assertIn("- Aplicado: não", text)
        self.assertIn("`body:bold`", text)

    def test_applied_font_real_and_typed(self):
        report = _report(_pkg(_paragraph(_run("font", half_points=22))), _font(12))
        self.assertIsInstance(report.applied_changes[0].desired_applied, LengthValue)
        text = _text(render_processing_report(report))
        self.assertIn("Tamanho da fonte", text)
        self.assertIn("- Antes: 11 pt", text)
        self.assertIn("- Aplicado: 12 pt", text)

    def test_applied_line_spacing_real(self):
        body = (
            '<w:p><w:pPr><w:pStyle w:val="Normal"/>'
            '<w:spacing w:line="480" w:lineRule="auto"/></w:pPr>'
            '<w:r><w:t>spacing</w:t></w:r></w:p>'
        )
        report = build_product_from_inputs(
            _pkg(body), _line_spacing(1.5)
        ).processing_report
        text = _text(render_processing_report(report))
        self.assertIn("Entrelinha", text)
        self.assertIn("- Antes: 2 linhas", text)
        self.assertIn("- Aplicado: 1.5 linhas", text)

    def test_review_line_spacing_real(self):
        body = (
            '<w:p><w:pPr><w:pStyle w:val="Normal"/>'
            '<w:spacing w:line="240" w:lineRule="exact"/></w:pPr>'
            '<w:r><w:t>spacing</w:t></w:r></w:p>'
        )
        report = build_product_from_inputs(
            _pkg(body), _line_spacing(1.5)
        ).processing_report
        self.assertEqual(len(report.review_items), 1)
        text = _text(render_processing_report(report))
        self.assertIn("- Observado: 12 pt (exact)", text)

    def test_unapplied_real_patch_rejection(self):
        report = _report(_pkg(_paragraph(_run("dup", bold_xml="<w:b/><w:b/>"))), _bold(False))
        self.assertEqual(len(report.unapplied_changes), 1)
        text = _text(render_processing_report(report))
        item = report.unapplied_changes[0]
        self.assertIn(f"`{item.reason}`", text)
        self.assertIn(f"`{item.finding_kind.value}`", text)
        self.assertNotIn("gravidade", text.lower())

    def test_review_item_real(self):
        run = '<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>review</w:t></w:r>'
        report = _report(_pkg(_paragraph(run)), _bold(False))
        self.assertEqual(len(report.review_items), 1)
        text = _text(render_processing_report(report))
        self.assertIn("## Itens para revisão", text)
        self.assertIn(f"`{report.review_items[0].reason.value}`", text)

    def test_analysis_reason_reaches_human_report(self):
        body = (
            '<w:p><w:pPr><w:pStyle w:val="Normal"/>'
            '<w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>lista</w:t></w:r></w:p>'
        )
        profile = json.dumps(
            {
                "schema_version": "0.3",
                "profile": {"id": "human-report-p3", "version": "1"},
                "rules": {"body": {"line_spacing": {"mode": "exact", "value": 1.5}}},
            },
            separators=(",", ":"),
        ).encode("utf-8")
        styles = NORMAL + (
            '<w:docDefaults><w:pPrDefault><w:pPr>'
            '<w:numPr><w:ilvl w:val="0"/></w:numPr>'
            '</w:pPr></w:pPrDefault></w:docDefaults>'
        )
        report = build_product_from_inputs(
            _pkg(body, styles=styles), profile
        ).processing_report
        self.assertEqual(len(report.review_items), 1)
        self.assertEqual(
            report.review_items[0].analysis_reason,
            "numbering_spacing_unsupported",
        )
        text = _text(render_processing_report(report))
        self.assertIn("numbering_spacing_unsupported", text)

    def test_classification_abstention_real(self):
        pkg = _pkg(_paragraph(_run("unknown"), style=False), styles="")
        report = _report(pkg, _bold(False))
        self.assertGreaterEqual(len(report.classification_items), 1)
        text = _text(render_processing_report(report))
        self.assertIn("## Observações de classificação", text)
        self.assertIn("`abstained`", text)

    def test_summary_counts_are_projection_not_recalculated_percentages(self):
        report = _report(_pkg(_paragraph(_run("bold", bold_xml="<w:b/>"))), _bold(False))
        text = _text(render_processing_report(report))
        s = report.summary
        self.assertIn(f"- Alterações aplicadas: {s.applied_change_count}", text)
        self.assertIn(f"- Classificações finais: {s.final_classification_count}", text)
        self.assertNotIn("%", text)


class HumanReportBindingAndModelTests(unittest.TestCase):
    def test_refs_hash_encoding_and_newline(self):
        report = _report(_pkg(_paragraph(_run("hash"))), _bold(False))
        rendered = render_processing_report(report)
        self.assertEqual(rendered.human_report_version, HUMAN_REPORT_VERSION)
        self.assertEqual(rendered.media_type, HUMAN_REPORT_MEDIA_TYPE)
        self.assertEqual(rendered.processing_report_ref, processing_report_ref(report))
        self.assertEqual(rendered.content_sha256, hashlib.sha256(rendered.content_bytes).hexdigest())
        self.assertFalse(rendered.content_bytes.startswith(b"\xef\xbb\xbf"))
        text = rendered.content_bytes.decode("utf-8", errors="strict")
        self.assertNotIn("\r", text)
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_model_rejects_bad_content_hash(self):
        report = _report(_pkg(_paragraph(_run("hash"))), _bold(False))
        rendered = render_processing_report(report)
        with self.assertRaises(ValueError):
            replace(rendered, content_sha256="0" * 64)

    def test_wrong_input_type_is_contract_error(self):
        for bad in (None, {}, b"x"):
            with self.subTest(type=type(bad).__name__):
                with self.assertRaises(HumanReportContractError):
                    render_processing_report(bad)  # type: ignore[arg-type]

    def test_input_report_not_mutated_and_repeat_is_byte_identical(self):
        report = _report(_pkg(_paragraph(_run("repeat", bold_xml="<w:b/>"))), _bold(False))
        before = report
        a = render_processing_report(report)
        b = render_processing_report(report)
        self.assertEqual(report, before)
        self.assertEqual(a, b)
        self.assertEqual(a.content_bytes, b.content_bytes)


class HumanReportValueAndEscapingTests(unittest.TestCase):
    def test_decimal_canonical_via_review_value(self):
        report = _report(_pkg(_paragraph('<w:r><w:rPr/><w:t>x</w:t></w:r>')), _font(12))
        self.assertEqual(len(report.review_items), 1)
        item = replace(report.review_items[0], observed=Decimal("11.5000"))
        altered = replace(report, review_items=(item,))
        text = _text(render_processing_report(altered))
        self.assertIn("- Observado: 11.5", text)

    def test_none_where_allowed_is_explicit(self):
        report = _report(_pkg(_paragraph('<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>x</w:t></w:r>')), _bold(False))
        item = replace(report.review_items[0], observed=None)
        altered = replace(report, review_items=(item,))
        self.assertIn("- Observado: não disponível", _text(render_processing_report(altered)))

    def test_markdown_hostile_structural_path_is_code_not_markup(self):
        report = _report(_pkg(_paragraph('<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>x</w:t></w:r>')), _bold(False))
        target = replace(report.review_items[0].target, structural_path="# h [x](javascript:y) `tick`\n* list")
        item = replace(report.review_items[0], target=target, decision_warnings=(DecisionWarning("w`#[]*", "ignored"),))
        altered = replace(report, review_items=(item,))
        text = _text(render_processing_report(altered))
        self.assertNotIn("\n* list\n", text)
        self.assertIn("\\n* list", text)
        self.assertIn("w`#[]*", text)

    def test_unexpected_value_type_is_integrity_error(self):
        report = _report(_pkg(_paragraph('<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>x</w:t></w:r>')), _bold(False))
        item = replace(report.review_items[0], observed=object())
        altered = replace(report, review_items=(item,))
        with self.assertRaises(HumanReportIntegrityError):
            render_processing_report(altered)


class HumanReportStaticAuditTests(unittest.TestCase):
    def test_runtime_has_no_forbidden_io_clock_random_locale_network_llm_or_dynamic_import(self):
        base = Path(__file__).resolve().parents[1] / "src" / "formatador_academico" / "human_report"
        forbidden_import_roots = {
            "os", "pathlib", "socket", "requests", "urllib", "time", "datetime",
            "random", "uuid", "subprocess", "importlib", "locale", "openai",
        }
        forbidden_calls = {"open", "eval", "exec", "__import__"}
        for path in sorted(base.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name.split(".")[0], forbidden_import_roots, path.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split(".")[0], forbidden_import_roots, path.name)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, forbidden_calls, path.name)

    def test_renderer_does_not_import_execution_engines(self):
        path = Path(__file__).resolve().parents[1] / "src" / "formatador_academico" / "human_report" / "renderer.py"
        source = path.read_text(encoding="utf-8")
        for forbidden in ("docx_parser", "analysis.", "classification.engine", "decision.engine", "patcher"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
