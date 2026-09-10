"""Product Input Boundary v0.1 tests (decision 0043)."""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from formatador_academico.product_input_boundary import (
    PRODUCT_INPUT_BOUNDARY_VERSION,
    ProductInputBoundaryContractError,
    ProductInputBoundaryIntegrityError,
    ProductInputBoundaryUnsupportedError,
    ProductInputStage,
    build_product_from_inputs,
)
from formatador_academico.product_output_bundle import (
    ProductOutputBundleIntegrityError,
    build_product_output_bundle,
)
from formatador_academico.profile_input import processing_profile_from_json
from formatador_academico.processing_session import ProcessingSessionStatus

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL


def _json(rules, *, schema="0.1", profile_id="product-input", version="1"):
    return json.dumps(
        {
            "schema_version": schema,
            "profile": {"id": profile_id, "version": version},
            "rules": rules,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _bold(value=False):
    return {"body": {"bold": {"mode": "exact", "value": value}}}


def _font(value=12):
    return {"body": {"font_size": {"mode": "exact", "value": value}}}


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


class ProductInputBoundaryRealFlowTests(unittest.TestCase):
    def test_no_change_e2e(self):
        pkg = _pkg(_paragraph(_run("ok")))
        bundle = build_product_from_inputs(pkg, _json(_bold(False)))
        self.assertEqual(bundle.product_output_bundle_version, "0.1")
        self.assertEqual(bundle.clean_package_bytes, pkg)
        self.assertEqual(bundle.review_package_bytes, pkg)
        self.assertEqual(bundle.session_status, ProcessingSessionStatus.QUIESCENT)

    def test_bold_change_e2e(self):
        pkg = _pkg(_paragraph(_run("bold", bold_xml="<w:b/>")))
        bundle = build_product_from_inputs(pkg, _json(_bold(False)))
        self.assertEqual(bundle.processing_report.summary.applied_change_count, 1)
        self.assertNotEqual(bundle.clean_package_bytes, pkg)
        self.assertNotEqual(bundle.review_package_bytes, bundle.clean_package_bytes)

    def test_font_change_e2e(self):
        pkg = _pkg(_paragraph(_run("font", half_points=22)))
        bundle = build_product_from_inputs(pkg, _json(_font(12)))
        self.assertEqual(bundle.processing_report.summary.applied_change_count, 1)

    def test_review_and_unapplied_are_preserved(self):
        review_pkg = _pkg(_paragraph('<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>review</w:t></w:r>'))
        review = build_product_from_inputs(review_pkg, _json(_bold(False)))
        self.assertEqual(review.processing_report.summary.review_item_count, 1)

        reject_pkg = _pkg(_paragraph(_run("dup", bold_xml="<w:b/><w:b/>")))
        rejected = build_product_from_inputs(reject_pkg, _json(_bold(False)))
        self.assertEqual(rejected.session_status, ProcessingSessionStatus.QUIESCENT_WITH_UNAPPLIED)
        self.assertEqual(rejected.processing_report.summary.unapplied_change_count, 1)

    def test_operation_limit_status_preserved(self):
        pkg = _pkg(_paragraph(_run("two", bold_xml="<w:b/>", half_points=22)))
        profile_json = _json({
            "body": {
                "bold": {"mode": "exact", "value": False},
                "font_size": {"mode": "exact", "value": 12},
            }
        })
        bundle = build_product_from_inputs(pkg, profile_json, max_applied_operations=1)
        self.assertEqual(bundle.session_status, ProcessingSessionStatus.OPERATION_LIMIT_REACHED)

    def test_wrapper_equals_manual_composition(self):
        pkg = _pkg(_paragraph(_run("manual", bold_xml="<w:b/>", half_points=22)))
        profile_json = _json({
            "body": {
                "bold": {"mode": "exact", "value": False},
                "font_size": {"mode": "exact", "value": 12},
            }
        })
        wrapped = build_product_from_inputs(pkg, profile_json)
        profile = processing_profile_from_json(profile_json)
        manual = build_product_output_bundle(pkg, profile)
        self.assertEqual(wrapped, manual)

    def test_semantically_equivalent_json_produces_same_bundle(self):
        pkg = _pkg(_paragraph(_run("canonical", half_points=22)))
        a = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"font_size":{"mode":"exact","value":12}}}}'
        b = b'{"rules":{"body":{"font_size":{"value":1.2e1,"mode":"exact"}}},"profile":{"version":"1","id":"p"},"schema_version":"0.1"}'
        self.assertEqual(build_product_from_inputs(pkg, a), build_product_from_inputs(pkg, b))

    def test_inputs_not_mutated_and_repeat_deterministic(self):
        pkg = _pkg(_paragraph(_run("repeat", bold_xml="<w:b/>")))
        profile_json = _json(_bold(False))
        before_pkg = bytes(pkg)
        before_json = bytes(profile_json)
        a = build_product_from_inputs(pkg, profile_json)
        b = build_product_from_inputs(pkg, profile_json)
        self.assertEqual(pkg, before_pkg)
        self.assertEqual(profile_json, before_json)
        self.assertEqual(a, b)


class ProductInputBoundaryErrorTests(unittest.TestCase):
    def test_external_type_order(self):
        with self.assertRaises(ProductInputBoundaryContractError) as cm:
            build_product_from_inputs("bad", "bad")  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "external_input.package_type")
        self.assertIs(cm.exception.stage, ProductInputStage.EXTERNAL_INPUT)

        with self.assertRaises(ProductInputBoundaryContractError) as cm:
            build_product_from_inputs(b"bad", "bad")  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "external_input.profile_type")

    def test_profile_contract_error_preserves_code_and_cause(self):
        pkg = _pkg(_paragraph(_run("x")))
        with self.assertRaises(ProductInputBoundaryContractError) as cm:
            build_product_from_inputs(pkg, b"{")
        self.assertTrue(cm.exception.code.startswith("profile_input."))
        self.assertIsNotNone(cm.exception.__cause__)
        self.assertIs(cm.exception.stage, ProductInputStage.PROFILE_INPUT)

    def test_profile_unsupported_preserves_code_and_cause(self):
        pkg = _pkg(_paragraph(_run("x")))
        with self.assertRaises(ProductInputBoundaryUnsupportedError) as cm:
            build_product_from_inputs(pkg, b'{"schema_version":"0.3"}')
        self.assertEqual(cm.exception.code, "profile_input.schema_version_unsupported")
        self.assertIsNotNone(cm.exception.__cause__)

    def test_invalid_docx_and_bad_limit_are_product_contract_errors(self):
        with self.assertRaises(ProductInputBoundaryContractError) as cm:
            build_product_from_inputs(b"not-docx", _json(_bold(False)))
        self.assertEqual(cm.exception.code, "product_output.contract")
        self.assertIs(cm.exception.stage, ProductInputStage.PRODUCT_OUTPUT)

        pkg = _pkg(_paragraph(_run("limit")))
        with self.assertRaises(ProductInputBoundaryContractError) as cm:
            build_product_from_inputs(pkg, _json(_bold(False)), max_applied_operations=0)
        self.assertEqual(cm.exception.code, "product_output.contract")

    def test_integrity_error_translation_preserves_cause(self):
        pkg = _pkg(_paragraph(_run("integrity")))
        with patch(
            "formatador_academico.product_input_boundary.builder.build_product_output_bundle",
            side_effect=ProductOutputBundleIntegrityError("synthetic"),
        ):
            with self.assertRaises(ProductInputBoundaryIntegrityError) as cm:
                build_product_from_inputs(pkg, _json(_bold(False)))
        self.assertEqual(cm.exception.code, "product_output.integrity")
        self.assertIsInstance(cm.exception.__cause__, ProductOutputBundleIntegrityError)

    def test_invalid_profile_never_reaches_product_output(self):
        pkg = _pkg(_paragraph(_run("profile-first")))
        with patch("formatador_academico.product_input_boundary.builder.build_product_output_bundle") as downstream:
            with self.assertRaises(ProductInputBoundaryUnsupportedError):
                build_product_from_inputs(pkg, b'{"schema_version":"0.3"}')
        downstream.assert_not_called()

    def test_unexpected_exception_is_not_masked(self):
        pkg = _pkg(_paragraph(_run("boom")))
        with patch(
            "formatador_academico.product_input_boundary.builder.processing_profile_from_json",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                build_product_from_inputs(pkg, _json(_bold(False)))


class ProductInputBoundaryStaticAuditTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(PRODUCT_INPUT_BOUNDARY_VERSION, "0.1")

    def test_runtime_has_no_forbidden_io_clock_random_network_or_dynamic_import(self):
        base = Path(__file__).resolve().parents[1] / "src" / "formatador_academico" / "product_input_boundary"
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
