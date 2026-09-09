"""Additional audit/integration tests for Profile Input v0.1."""
from __future__ import annotations

import unittest

from formatador_academico.product_output_bundle import build_product_output_bundle
from formatador_academico.profile_input import processing_profile_from_json

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL


def _pkg():
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
        '<w:r><w:rPr><w:b w:val="0"/></w:rPr><w:t>text</w:t></w:r></w:p>'
    )
    return build_docx(document(body), styles_part(NORMAL))


class SetCanonicalOrderAuditTests(unittest.TestCase):
    def test_allowed_order_is_semantically_canonical(self):
        left = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":{"mode":"set","allowed":[true,false]}}}}'
        right = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":{"mode":"set","allowed":[false,true]}}}}'
        self.assertEqual(
            processing_profile_from_json(left),
            processing_profile_from_json(right),
        )


class PreserveProductBehaviorAuditTests(unittest.TestCase):
    def test_preserve_only_is_valid_but_not_evidence_of_conformity(self):
        raw = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":{"mode":"preserve"}}}}'
        profile = processing_profile_from_json(raw)
        pkg = _pkg()
        bundle = build_product_output_bundle(pkg, profile)

        self.assertEqual(bundle.clean_package_bytes, pkg)
        self.assertEqual(bundle.review_package_bytes, pkg)
        report = bundle.processing_report
        self.assertEqual(report.summary.applied_change_count, 0)
        self.assertEqual(report.summary.unapplied_change_count, 0)
        self.assertEqual(report.summary.review_item_count, 0)
        self.assertEqual(len(report.applied_changes), 0)
        self.assertEqual(len(report.unapplied_changes), 0)
        self.assertEqual(len(report.review_items), 0)
        # Preserve is still an explicit internal Decision, so the summary may
        # distinguish it from complete rule omission. It is not conformity proof.
        self.assertGreater(report.summary.final_decision_count, 0)
