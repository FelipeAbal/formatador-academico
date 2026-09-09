"""Processing Report v0.1 tests (decision 0034)."""
from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from decimal import Decimal

from formatador_academico.classification import (
    ClassificationReason,
    ClassificationStatus,
    ClassificationWarning,
)
from formatador_academico.decision import Actionability, FormattingRule, RuleMode
from formatador_academico.processing_report import (
    PROCESSING_REPORT_VERSION,
    ClassificationItem,
    ProcessingReportContractError,
    ReviewItem,
    build_processing_report,
    processing_report_ref,
    serialize_processing_report,
)
from formatador_academico.processing_session import (
    ProcessingSessionStatus,
    RuleBinding,
    process_document,
)
from formatador_academico.transform_log import transform_ref

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


class ProcessingReportRealFlowTests(unittest.TestCase):
    def test_no_change_report(self):
        pkg = _pkg(_paragraph(_run("ok", bold=False, half_points=24)))
        session = process_document(pkg, _body_profile())
        report = build_processing_report(session)
        self.assertEqual(report.processing_report_version, PROCESSING_REPORT_VERSION)
        self.assertEqual(report.summary.session_status, ProcessingSessionStatus.QUIESCENT)
        self.assertEqual(report.applied_changes, ())
        self.assertEqual(report.unapplied_changes, ())
        self.assertEqual(report.summary.input_package_sha256, session.input_package_sha256)
        self.assertEqual(report.summary.output_package_sha256, session.output_package_sha256)

    def test_one_bold_applied(self):
        pkg = _pkg(_paragraph(_run("bold", bold=True, half_points=24)))
        session = process_document(
            pkg, _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        report = build_processing_report(session)
        self.assertEqual(len(report.applied_changes), 1)
        item = report.applied_changes[0]
        self.assertEqual(item.target.property_slot, "bold")
        self.assertIs(item.observed_before, True)
        self.assertIs(item.desired_applied, False)
        self.assertEqual(item.transform_ref, transform_ref(session.transforms[0]))
        self.assertEqual(item.target.target_class, "body")

    def test_one_font_applied_typed(self):
        pkg = _pkg(_paragraph(_run("font", bold=False, half_points=22)))
        session = process_document(
            pkg,
            _profile(RuleBinding("body", "run", _font_rule(Decimal("12")))),
        )
        report = build_processing_report(session)
        item = report.applied_changes[0]
        self.assertEqual(item.target.property_slot, "font_size")
        self.assertEqual(item.desired_applied.value, Decimal("12"))
        self.assertEqual(item.desired_applied.unit, "pt")

    def test_two_changes_preserve_transform_order(self):
        session = process_document(_two_change_pkg(), _body_profile())
        report = build_processing_report(session)
        self.assertEqual(
            [x.transform_ref for x in report.applied_changes],
            [transform_ref(x) for x in session.transforms],
        )
        self.assertEqual(
            [x.target.property_slot for x in report.applied_changes],
            ["bold", "font_size"],
        )

    def test_classification_abstention_becomes_item(self):
        table = (
            "<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w=\"1000\"/></w:tblGrid>"
            "<w:tr><w:tc><w:tcPr/>"
            + _paragraph(_run("cell", bold=True, half_points=24))
            + "</w:tc></w:tr></w:tbl>"
        )
        session = process_document(
            _pkg(table), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        report = build_processing_report(session)
        abstained = [
            x for x in session.final_classifications
            if x.status is ClassificationStatus.ABSTAINED
        ]
        self.assertEqual(len(report.classification_items), len(abstained))
        self.assertTrue(report.classification_items)
        self.assertTrue(all(isinstance(x, ClassificationItem) for x in report.classification_items))

    def test_review_decision_becomes_review_item(self):
        body = '<w:p><w:r><w:t>missing-size</w:t></w:r></w:p>'
        session = process_document(
            _pkg(body),
            _profile(RuleBinding("body", "run", _font_rule(Decimal("12")))),
        )
        reviews = [d for d in session.final_decisions if d.actionability is Actionability.REVIEW]
        self.assertTrue(reviews)
        report = build_processing_report(session)
        self.assertEqual(len(report.review_items), len(reviews))
        self.assertTrue(all(isinstance(x, ReviewItem) for x in report.review_items))

    def test_human_choice_becomes_review_item(self):
        rule = FormattingRule(
            "font-choice",
            "P2",
            "font_size",
            RuleMode.SET,
            allowed=(Decimal("12"), Decimal("13")),
        )
        pkg = _pkg(_paragraph(_run("choice", bold=False, half_points=22)))
        session = process_document(pkg, _profile(RuleBinding("body", "run", rule)))
        choices = [
            d for d in session.final_decisions
            if d.actionability is Actionability.HUMAN_CHOICE
        ]
        self.assertTrue(choices)
        report = build_processing_report(session)
        self.assertEqual(len(report.review_items), len(choices))
        self.assertTrue(all(x.actionability is Actionability.HUMAN_CHOICE for x in report.review_items))

    def test_no_action_does_not_become_review_item(self):
        pkg = _pkg(_paragraph(_run("ok", bold=False, half_points=24)))
        session = process_document(pkg, _body_profile())
        self.assertTrue(any(d.actionability is Actionability.NO_ACTION for d in session.final_decisions))
        report = build_processing_report(session)
        self.assertEqual(report.review_items, ())


class ProcessingReportClassificationTests(unittest.TestCase):
    def _base_session(self):
        pkg = _pkg(_paragraph(_run("ok", bold=False, half_points=24)))
        return process_document(pkg, _body_profile())

    def test_not_applicable_without_warning_is_summary_only(self):
        session = self._base_session()
        base = session.final_classifications[0]
        modified = replace(
            base,
            status=ClassificationStatus.NOT_APPLICABLE,
            target_class=None,
            basis=None,
            reasons=(ClassificationReason.UNSUPPORTED_TARGET,),
            evidence=(),
        )
        session = replace(session, final_classifications=(modified,))
        report = build_processing_report(session)
        self.assertEqual(report.classification_items, ())
        self.assertEqual(report.summary.not_applicable_count, 1)
        self.assertEqual(report.summary.story_coverage[0].not_applicable_count, 1)

    def test_classified_warning_becomes_item(self):
        session = self._base_session()
        base = session.final_classifications[0]
        warning = ClassificationWarning("x", "warning", base.structural_path)
        modified = replace(base, classification_warnings=(warning,))
        session = replace(session, final_classifications=(modified,))
        report = build_processing_report(session)
        self.assertEqual(len(report.classification_items), 1)
        self.assertEqual(report.summary.classification_warning_count, 1)

    def test_abstained_with_warning_is_single_item(self):
        table = (
            "<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w=\"1000\"/></w:tblGrid>"
            "<w:tr><w:tc><w:tcPr/>"
            + _paragraph(_run("cell", bold=True, half_points=24))
            + "</w:tc></w:tr></w:tbl>"
        )
        session = process_document(
            _pkg(table), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        idx = next(
            i for i, x in enumerate(session.final_classifications)
            if x.status is ClassificationStatus.ABSTAINED
        )
        original = session.final_classifications[idx]
        warning = ClassificationWarning("x", "warning", original.structural_path)
        modified = replace(original, classification_warnings=(warning,))
        values = list(session.final_classifications)
        values[idx] = modified
        session = replace(session, final_classifications=tuple(values))
        report = build_processing_report(session)
        matching = [x for x in report.classification_items if x.structural_path == original.structural_path]
        self.assertEqual(len(matching), 1)

    def test_story_coverage_sums_to_global(self):
        table = (
            "<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w=\"1000\"/></w:tblGrid>"
            "<w:tr><w:tc><w:tcPr/>"
            + _paragraph(_run("cell", bold=True, half_points=24))
            + "</w:tc></w:tr></w:tbl>"
        )
        session = process_document(
            _pkg(table), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        report = build_processing_report(session)
        coverage = report.summary.story_coverage
        self.assertEqual(sum(x.total_count for x in coverage), report.summary.final_classification_count)
        self.assertEqual(sum(x.abstained_count for x in coverage), report.summary.abstained_count)
        self.assertEqual(sum(x.not_applicable_count for x in coverage), report.summary.not_applicable_count)


class ProcessingReportSerializationTests(unittest.TestCase):
    def _report(self):
        session = process_document(_two_change_pkg(), _body_profile())
        return build_processing_report(session)

    def test_serialization_is_stable_utf8_json(self):
        report = self._report()
        a = serialize_processing_report(report)
        b = serialize_processing_report(report)
        self.assertEqual(a, b)
        decoded = json.loads(a.decode("utf-8"))
        self.assertEqual(decoded["processing_report_version"], "0.1")

    def test_report_ref_is_sha256_of_serialization(self):
        report = self._report()
        expected = hashlib.sha256(serialize_processing_report(report)).hexdigest()
        self.assertEqual(processing_report_ref(report), expected)

    def test_serialization_contains_no_package_bytes(self):
        report = self._report()
        payload = serialize_processing_report(report)
        self.assertNotIn(b"output_package_bytes", payload)
        self.assertNotIn(b"PK\x03\x04", payload)

    def test_decimal_and_lengthvalue_are_typed_not_humanized(self):
        pkg = _pkg(_paragraph(_run("font", bold=False, half_points=22)))
        session = process_document(
            pkg,
            _profile(RuleBinding("body", "run", _font_rule(Decimal("12")))),
        )
        report = build_processing_report(session)
        decoded = json.loads(serialize_processing_report(report).decode("utf-8"))
        desired = decoded["applied_changes"][0]["desired_applied"]
        self.assertEqual(desired, {"unit": "pt", "value": "12"})

    def test_target_class_preserved(self):
        report = self._report()
        self.assertTrue(report.applied_changes)
        self.assertTrue(all(x.target.target_class == "body" for x in report.applied_changes))


class ProcessingReportContractTests(unittest.TestCase):
    def test_wrong_input_type_rejected(self):
        with self.assertRaises(ProcessingReportContractError):
            build_processing_report(object())

    def test_input_session_not_mutated(self):
        session = process_document(_two_change_pkg(), _body_profile())
        before = session
        build_processing_report(session)
        self.assertEqual(session, before)

    def test_summary_counts_match_sources(self):
        session = process_document(_two_change_pkg(), _body_profile())
        report = build_processing_report(session)
        self.assertEqual(report.summary.applied_change_count, len(session.transforms))
        self.assertEqual(report.summary.unapplied_change_count, len(session.findings))
        self.assertEqual(report.summary.final_decision_count, len(session.final_decisions))
        self.assertEqual(report.summary.final_classification_count, len(session.final_classifications))


if __name__ == "__main__":
    unittest.main()
