"""Adversarial coverage for Review DOCX v0.1 / decision 0036."""
from __future__ import annotations

import ast
import hashlib
import io
import zipfile
import unittest
from dataclasses import replace
from decimal import Decimal

from lxml import etree

from formatador_academico.docx_parser import W_NS
from formatador_academico.processing_report import build_processing_report
from formatador_academico.processing_session import RuleBinding, process_document
from formatador_academico.review_docx import (
    ReviewDocxIntegrityError,
    ReviewMarkReason,
    build_review_docx,
)
from formatador_academico.review_docx.builder import _ordinary_reason
from formatador_academico.review_docx.validation import validate_allowed_delta

from test_processing_session_v01 import (
    _body_profile,
    _font_rule,
    _paragraph,
    _pkg,
    _profile,
    _run,
    _two_change_pkg,
)

W_R = f"{{{W_NS}}}r"


def _run_xml(inner: str) -> etree._Element:
    return etree.fromstring(
        (f'<w:r xmlns:w="{W_NS}">{inner}</w:r>').encode("utf-8")
    )


def _document_xml(pkg: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(pkg), "r") as zf:
        return zf.read("word/document.xml")


class SurfacePolicyAuditTests(unittest.TestCase):
    def test_empty_run_reason(self):
        reason, _ = _ordinary_reason(_run_xml(""))
        self.assertEqual(reason, ReviewMarkReason.NO_VISUAL_SURFACE)

    def test_rpr_only_reason(self):
        reason, _ = _ordinary_reason(_run_xml("<w:rPr><w:b/></w:rPr>"))
        self.assertEqual(reason, ReviewMarkReason.NO_VISUAL_SURFACE)

    def test_instrtext_only_reason(self):
        reason, _ = _ordinary_reason(_run_xml("<w:instrText>PAGE</w:instrText>"))
        self.assertEqual(reason, ReviewMarkReason.NO_VISUAL_SURFACE)

    def test_fldchar_only_reason(self):
        reason, _ = _ordinary_reason(_run_xml('<w:fldChar w:fldCharType="begin"/>'))
        self.assertEqual(reason, ReviewMarkReason.NO_VISUAL_SURFACE)

    def test_drawing_only_reason(self):
        reason, _ = _ordinary_reason(_run_xml("<w:drawing/>"))
        self.assertEqual(reason, ReviewMarkReason.NO_VISUAL_SURFACE)

    def test_deltext_reason(self):
        reason, _ = _ordinary_reason(_run_xml("<w:delText>x</w:delText>"))
        self.assertEqual(reason, ReviewMarkReason.PROTECTED_REVISION_RUN)

    def test_visible_text_has_no_ordinary_veto(self):
        reason, _ = _ordinary_reason(_run_xml("<w:t>x</w:t>"))
        self.assertIsNone(reason)

    def test_symbol_has_no_ordinary_veto(self):
        reason, _ = _ordinary_reason(_run_xml('<w:sym w:font="Wingdings" w:char="F0FC"/>'))
        self.assertIsNone(reason)

    def test_tab_and_break_have_no_ordinary_veto(self):
        self.assertIsNone(_ordinary_reason(_run_xml("<w:tab/>"))[0])
        self.assertIsNone(_ordinary_reason(_run_xml("<w:br/>"))[0])


class AsymmetricDeltaAuditTests(unittest.TestCase):
    def test_existing_highlight_overwrite_is_detected_when_unmarked(self):
        before = (
            f'<w:document xmlns:w="{W_NS}"><w:body><w:p><w:r><w:rPr>'
            '<w:highlight w:val="green"/></w:rPr><w:t>x</w:t></w:r></w:p>'
            '</w:body></w:document>'
        ).encode()
        after = before.replace(b'green', b'yellow')
        with self.assertRaises(ReviewDocxIntegrityError):
            validate_allowed_delta(before, after, ())

    def test_unrelated_text_mutation_is_detected(self):
        before = (
            f'<w:document xmlns:w="{W_NS}"><w:body><w:p><w:r><w:t>x</w:t></w:r></w:p>'
            '</w:body></w:document>'
        ).encode()
        after = before.replace(b'>x<', b'>y<')
        with self.assertRaises(ReviewDocxIntegrityError):
            validate_allowed_delta(before, after, ())


class IntegrityBindingAuditTests(unittest.TestCase):
    def test_final_review_item_physical_hash_mismatch_is_integrity_error(self):
        body = '<w:p><w:r><w:t>missing-size</w:t></w:r></w:p>'
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _font_rule(Decimal("12"))))
        )
        report = build_processing_report(session)
        self.assertTrue(report.review_items)
        item = report.review_items[0]
        bad_target = replace(item.target, physical_hash="0" * 64)
        bad_item = replace(item, target=bad_target)
        bad_report = replace(report, review_items=(bad_item,))
        with self.assertRaises(ReviewDocxIntegrityError):
            build_review_docx(session.output_package_bytes, bad_report)

    def test_final_review_item_missing_path_is_integrity_error(self):
        body = '<w:p><w:r><w:t>missing-size</w:t></w:r></w:p>'
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _font_rule(Decimal("12"))))
        )
        report = build_processing_report(session)
        item = report.review_items[0]
        bad_target = replace(item.target, structural_path="/w:document/w:body[1]/w:p[99]/w:r[1]")
        bad_item = replace(item, target=bad_target)
        bad_report = replace(report, review_items=(bad_item,))
        with self.assertRaises(ReviewDocxIntegrityError):
            build_review_docx(session.output_package_bytes, bad_report)


class DeterminismAuditTests(unittest.TestCase):
    def test_repeated_review_bytes_and_results_are_identical(self):
        session = process_document(_two_change_pkg(), _body_profile())
        report = build_processing_report(session)
        a = build_review_docx(session.output_package_bytes, report)
        b = build_review_docx(session.output_package_bytes, report)
        self.assertEqual(a.output_review_package_bytes, b.output_review_package_bytes)
        self.assertEqual(a.mark_results, b.mark_results)

    def test_runtime_has_no_forbidden_io_clock_random_network_or_dynamic_import(self):
        import formatador_academico.review_docx.builder as builder
        import formatador_academico.review_docx.validation as validation

        forbidden_modules = {
            "os", "pathlib", "socket", "requests", "urllib", "http", "time",
            "datetime", "random", "uuid", "subprocess",
        }
        for module in (builder, validation):
            with open(module.__file__, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".")[0] for alias in node.names}
                    self.assertTrue(roots.isdisjoint(forbidden_modules), (module.__name__, roots))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split(".")[0], forbidden_modules)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"__import__", "eval", "exec", "open"})


if __name__ == "__main__":
    unittest.main()
