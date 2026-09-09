"""Product Output Bundle v0.1 tests (decision 0038)."""
from __future__ import annotations

import ast
import hashlib
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from formatador_academico.decision import FormattingRule, ProfileRef, RuleMode
from formatador_academico.processing_report import serialize_processing_report
from formatador_academico.processing_session import (
    ProcessingProfile,
    ProcessingSessionContractError,
    ProcessingSessionIntegrityError,
    ProcessingSessionStatus,
    RuleBinding,
)
from formatador_academico.product_output_bundle import (
    PRODUCT_OUTPUT_BUNDLE_VERSION,
    ProductOutputBundleContractError,
    ProductOutputBundleIntegrityError,
    build_product_output_bundle,
)

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL

PROFILE_REF = ProfileRef("bundle-profile", "1")


def _bold_rule(expected=False, rule_id="body-bold"):
    return FormattingRule(rule_id, "P1", "bold", RuleMode.EXACT, expected=expected)


def _font_rule(expected=Decimal("12"), rule_id="body-font"):
    return FormattingRule(rule_id, "P2", "font_size", RuleMode.EXACT, expected=expected)


def _profile(*bindings):
    return ProcessingProfile(PROFILE_REF, tuple(bindings))


def _body_profile(*, order="bold-font"):
    b = RuleBinding("body", "run", _bold_rule(False))
    f = RuleBinding("body", "run", _font_rule(Decimal("12")))
    return _profile(*(b, f) if order == "bold-font" else (f, b))


def _run(text, *, bold_xml='<w:b w:val="0"/>', half_points=24):
    return (
        "<w:r><w:rPr>"
        + bold_xml
        + f'<w:sz w:val="{half_points}"/>'
        + f"</w:rPr><w:t>{text}</w:t></w:r>"
    )


def _paragraph(*runs):
    return '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>' + "".join(runs) + "</w:p>"


def _pkg(body):
    return build_docx(document(body), styles_part(NORMAL))


class ProductOutputBundleRealFlowTests(unittest.TestCase):
    def _assert_bindings(self, pkg, bundle):
        self.assertEqual(bundle.product_output_bundle_version, PRODUCT_OUTPUT_BUNDLE_VERSION)
        self.assertEqual(bundle.input_package_sha256, hashlib.sha256(pkg).hexdigest())
        self.assertEqual(bundle.clean_package_sha256, hashlib.sha256(bundle.clean_package_bytes).hexdigest())
        self.assertEqual(bundle.review_package_sha256, hashlib.sha256(bundle.review_package_bytes).hexdigest())
        self.assertEqual(bundle.processing_report_json_bytes, serialize_processing_report(bundle.processing_report))
        self.assertEqual(bundle.processing_report_ref, hashlib.sha256(bundle.processing_report_json_bytes).hexdigest())
        self.assertEqual(bundle.processing_report.summary.output_package_sha256, bundle.clean_package_sha256)

    def test_no_change_returns_three_bound_outputs(self):
        pkg = _pkg(_paragraph(_run("ok")))
        bundle = build_product_output_bundle(pkg, _body_profile())
        self._assert_bindings(pkg, bundle)
        self.assertEqual(bundle.session_status, ProcessingSessionStatus.QUIESCENT)
        self.assertEqual(bundle.clean_package_bytes, pkg)
        self.assertEqual(bundle.review_package_bytes, pkg)

    def test_real_bold_change(self):
        pkg = _pkg(_paragraph(_run("bold", bold_xml="<w:b/>")))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        bundle = build_product_output_bundle(pkg, profile)
        self._assert_bindings(pkg, bundle)
        self.assertNotEqual(bundle.clean_package_bytes, pkg)
        self.assertNotEqual(bundle.review_package_bytes, bundle.clean_package_bytes)
        self.assertEqual(bundle.processing_report.summary.applied_change_count, 1)

    def test_real_font_change(self):
        pkg = _pkg(_paragraph(_run("font", half_points=22)))
        profile = _profile(RuleBinding("body", "run", _font_rule(Decimal("12"))))
        bundle = build_product_output_bundle(pkg, profile)
        self._assert_bindings(pkg, bundle)
        self.assertEqual(bundle.processing_report.summary.applied_change_count, 1)
        self.assertNotEqual(bundle.review_package_bytes, bundle.clean_package_bytes)

    def test_real_review_item(self):
        run = '<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>review</w:t></w:r>'
        pkg = _pkg(_paragraph(run))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        bundle = build_product_output_bundle(pkg, profile)
        self._assert_bindings(pkg, bundle)
        self.assertEqual(bundle.processing_report.summary.review_item_count, 1)
        self.assertNotEqual(bundle.review_package_bytes, bundle.clean_package_bytes)

    def test_real_patch_rejection_is_published_in_report_and_review(self):
        pkg = _pkg(_paragraph(_run("dup", bold_xml="<w:b/><w:b/>")))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        bundle = build_product_output_bundle(pkg, profile)
        self._assert_bindings(pkg, bundle)
        self.assertEqual(bundle.session_status, ProcessingSessionStatus.QUIESCENT_WITH_UNAPPLIED)
        self.assertEqual(bundle.processing_report.summary.unapplied_change_count, 1)
        self.assertNotEqual(bundle.review_package_bytes, bundle.clean_package_bytes)

    def test_operation_limit_status_is_preserved(self):
        pkg = _pkg(_paragraph(_run("two", bold_xml="<w:b/>", half_points=22)))
        bundle = build_product_output_bundle(pkg, _body_profile(), max_applied_operations=1)
        self._assert_bindings(pkg, bundle)
        self.assertEqual(bundle.session_status, ProcessingSessionStatus.OPERATION_LIMIT_REACHED)
        self.assertEqual(bundle.processing_report.summary.applied_change_count, 1)
        self.assertEqual(bundle.processing_report.summary.unapplied_change_count, 1)

    def test_input_and_profile_are_not_mutated(self):
        pkg = _pkg(_paragraph(_run("immutable", bold_xml="<w:b/>")))
        profile = _body_profile()
        before_pkg = bytes(pkg)
        before_bindings = profile.bindings
        build_product_output_bundle(pkg, profile)
        self.assertEqual(pkg, before_pkg)
        self.assertEqual(profile.bindings, before_bindings)

    def test_binding_order_equivalence(self):
        pkg = _pkg(_paragraph(_run("order", bold_xml="<w:b/>", half_points=22)))
        a = build_product_output_bundle(pkg, _body_profile(order="bold-font"))
        b = build_product_output_bundle(pkg, _body_profile(order="font-bold"))
        self.assertEqual(a.clean_package_bytes, b.clean_package_bytes)
        self.assertEqual(a.review_package_bytes, b.review_package_bytes)
        self.assertEqual(a.processing_report_json_bytes, b.processing_report_json_bytes)

    def test_repeated_calls_are_byte_deterministic(self):
        pkg = _pkg(_paragraph(_run("repeat", bold_xml="<w:b/>", half_points=22)))
        profile = _body_profile()
        a = build_product_output_bundle(pkg, profile)
        b = build_product_output_bundle(pkg, profile)
        self.assertEqual(a, b)
        self.assertEqual(a.clean_package_bytes, b.clean_package_bytes)
        self.assertEqual(a.review_package_bytes, b.review_package_bytes)
        self.assertEqual(a.processing_report_json_bytes, b.processing_report_json_bytes)


class ProductOutputBundleErrorBoundaryTests(unittest.TestCase):
    def test_invalid_snapshot_translates_contract_error(self):
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        with self.assertRaises(ProductOutputBundleContractError):
            build_product_output_bundle(b"not-a-docx", profile)

    def test_bad_limit_translates_contract_error(self):
        pkg = _pkg(_paragraph(_run("limit")))
        with self.assertRaises(ProductOutputBundleContractError):
            build_product_output_bundle(pkg, _body_profile(), max_applied_operations=0)

    def test_processing_session_contract_error_preserves_cause(self):
        pkg = _pkg(_paragraph(_run("contract")))
        with patch(
            "formatador_academico.product_output_bundle.builder.process_document",
            side_effect=ProcessingSessionContractError("synthetic contract"),
        ):
            with self.assertRaises(ProductOutputBundleContractError) as caught:
                build_product_output_bundle(pkg, _body_profile())
        self.assertIsInstance(caught.exception.__cause__, ProcessingSessionContractError)

    def test_processing_session_integrity_error_preserves_cause(self):
        pkg = _pkg(_paragraph(_run("integrity")))
        with patch(
            "formatador_academico.product_output_bundle.builder.process_document",
            side_effect=ProcessingSessionIntegrityError("synthetic integrity"),
        ):
            with self.assertRaises(ProductOutputBundleIntegrityError) as caught:
                build_product_output_bundle(pkg, _body_profile())
        self.assertIsInstance(caught.exception.__cause__, ProcessingSessionIntegrityError)


class ProductOutputBundleStaticAuditTests(unittest.TestCase):
    def test_runtime_has_no_forbidden_io_clock_random_network_or_dynamic_import(self):
        base = Path(__file__).resolve().parents[1] / "src" / "formatador_academico" / "product_output_bundle"
        forbidden_import_roots = {"os", "pathlib", "socket", "requests", "urllib", "time", "datetime", "random", "uuid", "subprocess", "importlib"}
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


if __name__ == "__main__":
    unittest.main()
