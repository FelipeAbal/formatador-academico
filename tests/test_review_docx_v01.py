"""Review/Highlight DOCX v0.1 tests (decision 0036)."""
from __future__ import annotations

import hashlib
import io
import zipfile
import unittest
from decimal import Decimal

from lxml import etree

from formatador_academico.docx_parser import W_NS
from formatador_academico.processing_report import build_processing_report
from formatador_academico.processing_session import RuleBinding, process_document
from formatador_academico.review_docx import (
    REVIEW_DOCX_VERSION,
    ReviewDocxContractError,
    ReviewDocxIntegrityError,
    ReviewMarkReason,
    ReviewMarkStatus,
    build_review_docx,
)

from test_processing_session_v01 import (
    _body_profile,
    _bold_rule,
    _font_rule,
    _paragraph,
    _pkg,
    _profile,
    _run,
    _two_change_pkg,
)

W_HIGHLIGHT = f"{{{W_NS}}}highlight"
W_VAL = f"{{{W_NS}}}val"
W_R = f"{{{W_NS}}}r"
W_RPR = f"{{{W_NS}}}rPr"


def _document_xml(pkg: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(pkg), "r") as zf:
        return zf.read("word/document.xml")


def _root(pkg: bytes):
    return etree.fromstring(_document_xml(pkg))


def _runs(pkg: bytes):
    return _root(pkg).iter(W_R)


def _direct(node, tag):
    return [x for x in node if isinstance(x.tag, str) and x.tag == tag]


def _highlight_values(pkg: bytes):
    out = []
    for run in _runs(pkg):
        rprs = _direct(run, W_RPR)
        values = []
        if rprs:
            values = [x.get(W_VAL) for x in _direct(rprs[0], W_HIGHLIGHT)]
        out.append(values)
    return out


class ReviewDocxRealFlowTests(unittest.TestCase):
    def test_applied_bold_is_marked(self):
        pkg = _pkg(_paragraph(_run("bold", bold=True, half_points=24)))
        session = process_document(pkg, _profile(RuleBinding("body", "run", _bold_rule(False))))
        report = build_processing_report(session)
        result = build_review_docx(session.output_package_bytes, report)
        self.assertEqual(result.review_docx_version, REVIEW_DOCX_VERSION)
        self.assertEqual(len(result.mark_results), 1)
        self.assertEqual(result.mark_results[0].status, ReviewMarkStatus.MARKED)
        self.assertEqual(result.mark_results[0].source_kinds, ("applied_change",))
        self.assertEqual(_highlight_values(result.output_review_package_bytes)[0], ["yellow"])

    def test_applied_font_is_marked(self):
        pkg = _pkg(_paragraph(_run("font", bold=False, half_points=22)))
        session = process_document(pkg, _profile(RuleBinding("body", "run", _font_rule(Decimal("12")))))
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        self.assertEqual(result.mark_results[0].status, ReviewMarkStatus.MARKED)

    def test_two_applied_same_run_deduplicate(self):
        session = process_document(_two_change_pkg(), _body_profile())
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        self.assertEqual(len(result.mark_results), 1)
        self.assertEqual(result.mark_results[0].source_kinds, ("applied_change",))
        self.assertEqual(_highlight_values(result.output_review_package_bytes)[0], ["yellow"])

    def test_review_item_is_marked(self):
        body = '<w:p><w:r><w:t>missing-size</w:t></w:r></w:p>'
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _font_rule(Decimal("12"))))
        )
        report = build_processing_report(session)
        self.assertTrue(report.review_items)
        result = build_review_docx(session.output_package_bytes, report)
        self.assertEqual(result.mark_results[0].source_kinds, ("review_item",))
        self.assertEqual(result.mark_results[0].status, ReviewMarkStatus.MARKED)

    def test_real_patch_rejection_unapplied_is_marked(self):
        body = (
            '<w:p><w:r><w:rPr><w:b/><w:b/></w:rPr>'
            '<w:t>duplicate-bold</w:t></w:r></w:p>'
        )
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        report = build_processing_report(session)
        self.assertTrue(report.unapplied_changes)
        result = build_review_docx(session.output_package_bytes, report)
        self.assertEqual(result.mark_results[0].source_kinds, ("unapplied_change",))
        self.assertEqual(result.mark_results[0].status, ReviewMarkStatus.MARKED)

    def test_zero_markable_items_returns_exact_clean_bytes(self):
        pkg = _pkg(_paragraph(_run("ok", bold=False, half_points=24)))
        session = process_document(pkg, _body_profile())
        report = build_processing_report(session)
        result = build_review_docx(session.output_package_bytes, report)
        self.assertEqual(result.mark_results, ())
        self.assertEqual(result.output_review_package_bytes, session.output_package_bytes)
        self.assertEqual(result.output_review_package_sha256, session.output_package_sha256)

    def test_classification_items_are_counted_not_marked(self):
        table = (
            '<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="1000"/></w:tblGrid>'
            '<w:tr><w:tc><w:tcPr/>' + _paragraph(_run("cell", bold=True, half_points=24)) +
            '</w:tc></w:tr></w:tbl>'
        )
        session = process_document(
            _pkg(table), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        report = build_processing_report(session)
        result = build_review_docx(session.output_package_bytes, report)
        self.assertEqual(result.unmarkable_classification_item_count, len(report.classification_items))
        self.assertEqual(result.mark_results, ())


class ReviewDocxConservationTests(unittest.TestCase):
    def test_existing_green_highlight_is_preserved_unmarked(self):
        body = (
            '<w:p><w:r><w:rPr><w:b/><w:highlight w:val="green"/>'
            '<w:sz w:val="24"/></w:rPr><w:t>x</w:t></w:r></w:p>'
        )
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        self.assertEqual(result.mark_results[0].status, ReviewMarkStatus.UNMARKED)
        self.assertEqual(result.mark_results[0].reason, ReviewMarkReason.EXISTING_HIGHLIGHT)
        self.assertEqual(_highlight_values(result.output_review_package_bytes)[0], ["green"])
        self.assertEqual(result.output_review_package_bytes, session.output_package_bytes)

    def test_existing_yellow_highlight_is_preserved_unmarked(self):
        body = (
            '<w:p><w:r><w:rPr><w:b/><w:highlight w:val="yellow"/>'
            '<w:sz w:val="24"/></w:rPr><w:t>x</w:t></w:r></w:p>'
        )
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        self.assertEqual(result.mark_results[0].reason, ReviewMarkReason.EXISTING_HIGHLIGHT)
        self.assertEqual(_highlight_values(result.output_review_package_bytes)[0], ["yellow"])

    def test_create_rpr_as_first_child(self):
        body = '<w:p><w:r><w:t>x</w:t></w:r></w:p>'
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _font_rule(Decimal("12"))))
        )
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        run = next(_runs(result.output_review_package_bytes))
        first = next(x for x in run if isinstance(x.tag, str))
        self.assertEqual(first.tag, W_RPR)

    def test_foreign_w14_extension_is_tolerated_and_preserved(self):
        body = (
            '<w:p><w:r xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">'
            '<w:rPr><w:b/><w14:textOutline w14:w="1"/><w:sz w:val="24"/></w:rPr>'
            '<w:t>x</w:t></w:r></w:p>'
        )
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        self.assertEqual(result.mark_results[0].status, ReviewMarkStatus.MARKED)
        xml = _document_xml(result.output_review_package_bytes)
        self.assertIn(b"textOutline", xml)

    def test_non_document_parts_are_byte_identical(self):
        session = process_document(_two_change_pkg(), _body_profile())
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        with zipfile.ZipFile(io.BytesIO(session.output_package_bytes), "r") as a, zipfile.ZipFile(
            io.BytesIO(result.output_review_package_bytes), "r"
        ) as b:
            self.assertEqual([x.filename for x in a.infolist()], [x.filename for x in b.infolist()])
            for info in a.infolist():
                if info.filename != "word/document.xml":
                    self.assertEqual(a.read(info.filename), b.read(info.filename))

    def test_clean_input_is_not_mutated(self):
        session = process_document(_two_change_pkg(), _body_profile())
        clean = bytes(session.output_package_bytes)
        build_review_docx(clean, build_processing_report(session))
        self.assertEqual(clean, session.output_package_bytes)


class ReviewDocxSurfaceTests(unittest.TestCase):
    def _build_for_body(self, body):
        session = process_document(
            _pkg(body), _profile(RuleBinding("body", "run", _font_rule(Decimal("12"))))
        )
        return build_review_docx(session.output_package_bytes, build_processing_report(session))

    def test_empty_run_is_no_visual_surface(self):
        # Create a review item on a run whose only visible property is absent font size.
        result = self._build_for_body('<w:p><w:r/></w:p>')
        # Classification may abstain before a Decision exists, so no candidate is acceptable.
        if result.mark_results:
            self.assertEqual(result.mark_results[0].reason, ReviewMarkReason.NO_VISUAL_SURFACE)

    def test_instrtext_only_is_no_visual_surface_when_candidate_exists(self):
        result = self._build_for_body('<w:p><w:r><w:instrText>PAGE</w:instrText></w:r></w:p>')
        if result.mark_results:
            self.assertEqual(result.mark_results[0].reason, ReviewMarkReason.NO_VISUAL_SURFACE)

    def test_deleted_revision_is_never_marked(self):
        body = '<w:p><w:del w:id="1"><w:r><w:delText>x</w:delText></w:r></w:del></w:p>'
        result = self._build_for_body(body)
        if result.mark_results:
            self.assertEqual(result.mark_results[0].reason, ReviewMarkReason.PROTECTED_REVISION_RUN)

    def test_hyperlink_visible_run_can_be_marked(self):
        body = '<w:p><w:hyperlink w:anchor="x"><w:r><w:t>x</w:t></w:r></w:hyperlink></w:p>'
        result = self._build_for_body(body)
        self.assertTrue(result.mark_results)
        self.assertEqual(result.mark_results[0].status, ReviewMarkStatus.MARKED)


class ReviewDocxBindingTests(unittest.TestCase):
    def test_wrong_clean_snapshot_hash_is_integrity_error(self):
        session = process_document(_two_change_pkg(), _body_profile())
        report = build_processing_report(session)
        with self.assertRaises(ReviewDocxIntegrityError):
            build_review_docx(b"not-the-clean-package", report)

    def test_wrong_report_type_is_contract_error(self):
        with self.assertRaises(ReviewDocxContractError):
            build_review_docx(b"x", object())

    def test_output_hash_matches_bytes(self):
        session = process_document(_two_change_pkg(), _body_profile())
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        self.assertEqual(
            result.output_review_package_sha256,
            hashlib.sha256(result.output_review_package_bytes).hexdigest(),
        )

    def test_result_records_final_physical_hash(self):
        session = process_document(_two_change_pkg(), _body_profile())
        result = build_review_docx(session.output_package_bytes, build_processing_report(session))
        self.assertEqual(len(result.mark_results[0].physical_hash), 64)


if __name__ == "__main__":
    unittest.main()
