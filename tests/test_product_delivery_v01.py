"""Product Delivery / File Naming v0.1 tests (decision 0047)."""
from __future__ import annotations

import ast
import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path

from formatador_academico.human_report import render_processing_report
from formatador_academico.product_delivery import (
    DOCX_MEDIA_TYPE,
    JSON_MEDIA_TYPE,
    MARKDOWN_MEDIA_TYPE,
    PRODUCT_DELIVERY_VERSION,
    DeliveryFile,
    DeliveryRole,
    ProductDelivery,
    ProductDeliveryContractError,
    ROLE_ORDER,
    build_product_delivery,
    canonicalize_delivery_base_name,
    filename_for_role,
    product_output_bundle_ref,
)
from formatador_academico.product_input_boundary import build_product_from_inputs

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL


def _json(rules):
    return json.dumps(
        {
            "schema_version": "0.1",
            "profile": {"id": "delivery", "version": "1"},
            "rules": rules,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _bold(value=False):
    return {"body": {"bold": {"mode": "exact", "value": value}}}


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


def _bundle(*, bold_xml='<w:b w:val="0"/>'):
    pkg = _pkg(_paragraph(_run("delivery", bold_xml=bold_xml)))
    return build_product_from_inputs(pkg, _json(_bold(False)))


class BaseNameTests(unittest.TestCase):
    def test_types_lengths_empty_null_and_hidden(self):
        for bad in (None, b"x", 3):
            with self.subTest(bad=bad):
                with self.assertRaises(ProductDeliveryContractError):
                    canonicalize_delivery_base_name(bad)  # type: ignore[arg-type]
        for bad in ("", " " * 3, "...", "\x00x", ".artigo", "..x"):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ProductDeliveryContractError):
                    canonicalize_delivery_base_name(bad)
        with self.assertRaises(ProductDeliveryContractError):
            canonicalize_delivery_base_name("x" * 121)

    def test_path_and_windows_chars_are_sanitized(self):
        with self.assertRaises(ProductDeliveryContractError):
            canonicalize_delivery_base_name(" ../artigo\\versao:1?*<>| ")
        result = canonicalize_delivery_base_name("a\x01b/c")
        self.assertEqual(result, "a_b_c")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)

    def test_whitespace_underscore_trailing_canonicalization(self):
        self.assertEqual(canonicalize_delivery_base_name("  meu\t\n artigo___final...  "), "meu artigo_final")

    def test_reserved_windows_devices(self):
        for bad in ("CON", "con.txt", "PrN.foo", "AUX", "nul.docx", "COM1", "com9.any", "LPT1", "lpt9.x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ProductDeliveryContractError):
                    canonicalize_delivery_base_name(bad)

    def test_unicode_preserved_without_normalization(self):
        composed = canonicalize_delivery_base_name("café")
        decomposed = canonicalize_delivery_base_name("cafe\u0301")
        self.assertEqual(composed, "café")
        self.assertEqual(decomposed, "cafe\u0301")
        self.assertNotEqual(composed, decomposed)

    def test_truncation_100_codepoints(self):
        raw = "a" * 120
        self.assertEqual(canonicalize_delivery_base_name(raw), "a" * 100)
        self.assertEqual(len(canonicalize_delivery_base_name(raw)), 100)


class DeliveryRealFlowTests(unittest.TestCase):
    def test_no_change_five_files_and_exact_sources(self):
        bundle = _bundle()
        delivery = build_product_delivery(bundle, base_name="Meu Artigo")
        self.assertEqual(delivery.product_delivery_version, PRODUCT_DELIVERY_VERSION)
        self.assertEqual(delivery.base_name, "Meu Artigo")
        self.assertEqual(tuple(f.role for f in delivery.files), ROLE_ORDER)
        expected_names = (
            "Meu Artigo_limpo.docx",
            "Meu Artigo_revisao.docx",
            "Meu Artigo_relatorio.json",
            "Meu Artigo_relatorio.md",
            "Meu Artigo_manifest.json",
        )
        self.assertEqual(tuple(f.filename for f in delivery.files), expected_names)
        self.assertEqual(delivery.files[0].content_bytes, bundle.clean_package_bytes)
        self.assertEqual(delivery.files[1].content_bytes, bundle.review_package_bytes)
        self.assertEqual(delivery.files[2].content_bytes, bundle.processing_report_json_bytes)
        human = render_processing_report(bundle.processing_report)
        self.assertEqual(delivery.files[3].content_bytes, human.content_bytes)
        self.assertEqual(delivery.human_report_ref, human.content_sha256)

    def test_applied_change_real_flow(self):
        bundle = _bundle(bold_xml="<w:b/>")
        delivery = build_product_delivery(bundle, base_name="artigo")
        self.assertNotEqual(bundle.clean_package_bytes, bundle.review_package_bytes)
        self.assertEqual(delivery.files[0].content_bytes, bundle.clean_package_bytes)
        self.assertEqual(delivery.files[1].content_bytes, bundle.review_package_bytes)
        self.assertIn("Alterações aplicadas", delivery.files[3].content_bytes.decode("utf-8"))

    def test_review_and_unapplied_real_flow(self):
        review_pkg = _pkg(_paragraph('<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>review</w:t></w:r>'))
        review_bundle = build_product_from_inputs(review_pkg, _json(_bold(False)))
        review_delivery = build_product_delivery(review_bundle, base_name="review")
        self.assertIn("Itens para revisão", review_delivery.files[3].content_bytes.decode("utf-8"))

        reject_pkg = _pkg(_paragraph(_run("dup", bold_xml="<w:b/><w:b/>")))
        reject_bundle = build_product_from_inputs(reject_pkg, _json(_bold(False)))
        rejected = build_product_delivery(reject_bundle, base_name="reject")
        self.assertIn("Alterações não aplicadas", rejected.files[3].content_bytes.decode("utf-8"))

    def test_hash_size_media_and_filename_safety(self):
        delivery = build_product_delivery(_bundle(), base_name="artigo/teste")
        self.assertEqual(delivery.base_name, "artigo_teste")
        for item in delivery.files:
            self.assertEqual(item.content_sha256, hashlib.sha256(item.content_bytes).hexdigest())
            self.assertEqual(item.size_bytes, len(item.content_bytes))
            self.assertNotIn("/", item.filename)
            self.assertNotIn("\\", item.filename)
            self.assertFalse(item.filename.startswith("."))
            self.assertLessEqual(len(item.filename), 140)
        self.assertEqual(delivery.files[0].media_type, DOCX_MEDIA_TYPE)
        self.assertEqual(delivery.files[1].media_type, DOCX_MEDIA_TYPE)
        self.assertEqual(delivery.files[2].media_type, JSON_MEDIA_TYPE)
        self.assertEqual(delivery.files[3].media_type, MARKDOWN_MEDIA_TYPE)
        self.assertEqual(delivery.files[4].media_type, JSON_MEDIA_TYPE)

    def test_bundle_ref_matches_canonical_payload(self):
        bundle = _bundle()
        payload = {
            "product_output_bundle_version": bundle.product_output_bundle_version,
            "input_package_sha256": bundle.input_package_sha256,
            "clean_package_sha256": bundle.clean_package_sha256,
            "review_package_sha256": bundle.review_package_sha256,
            "processing_report_ref": bundle.processing_report_ref,
            "profile_id": bundle.profile_ref.profile_id,
            "profile_version": bundle.profile_ref.profile_version,
            "session_status": bundle.session_status.value,
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = hashlib.sha256(canonical).hexdigest()
        self.assertEqual(product_output_bundle_ref(bundle), expected)
        self.assertEqual(build_product_delivery(bundle, base_name="x").product_output_bundle_ref, expected)

    def test_manifest_exactly_binds_first_four_files(self):
        delivery = build_product_delivery(_bundle(), base_name="manifesto")
        manifest = json.loads(delivery.files[4].content_bytes.decode("utf-8"))
        self.assertEqual(set(manifest), {"product_delivery_version", "base_name", "product_output_bundle_ref", "human_report_ref", "files"})
        self.assertEqual(len(manifest["files"]), 4)
        self.assertNotIn("manifest", [x["role"] for x in manifest["files"]])
        for meta, item in zip(manifest["files"], delivery.files[:4]):
            self.assertEqual(meta["role"], item.role.value)
            self.assertEqual(meta["filename"], item.filename)
            self.assertEqual(meta["media_type"], item.media_type)
            self.assertEqual(meta["sha256"], item.content_sha256)
            self.assertEqual(meta["size_bytes"], item.size_bytes)
        raw = delivery.files[4].content_bytes
        self.assertEqual(raw, json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        lower = raw.lower()
        for forbidden in (b"timestamp", b"hostname", b"username", b"/home/", b"c:\\"):
            self.assertNotIn(forbidden, lower)

    def test_inputs_not_mutated_and_repeat_deterministic(self):
        bundle = _bundle(bold_xml="<w:b/>")
        before = bundle
        a = build_product_delivery(bundle, base_name=" artigo ")
        b = build_product_delivery(bundle, base_name="artigo")
        self.assertEqual(bundle, before)
        self.assertEqual(a, b)
        self.assertEqual(tuple(x.content_bytes for x in a.files), tuple(x.content_bytes for x in b.files))


class DeliveryModelInvariantTests(unittest.TestCase):
    def test_wrong_bundle_type_is_contract_error(self):
        with self.assertRaises(ProductDeliveryContractError):
            build_product_delivery(object(), base_name="x")  # type: ignore[arg-type]

    def test_delivery_file_rejects_bad_hash_size_media_and_path(self):
        content = b"x"
        good_sha = hashlib.sha256(content).hexdigest()
        with self.assertRaises(ValueError):
            DeliveryFile(DeliveryRole.CLEAN_DOCX, "x_limpo.docx", DOCX_MEDIA_TYPE, content, "0" * 64, 1)
        with self.assertRaises(ValueError):
            DeliveryFile(DeliveryRole.CLEAN_DOCX, "x_limpo.docx", DOCX_MEDIA_TYPE, content, good_sha, 2)
        with self.assertRaises(ValueError):
            DeliveryFile(DeliveryRole.CLEAN_DOCX, "../x.docx", DOCX_MEDIA_TYPE, content, good_sha, 1)
        with self.assertRaises(ValueError):
            DeliveryFile(DeliveryRole.CLEAN_DOCX, "x_limpo.docx", JSON_MEDIA_TYPE, content, good_sha, 1)

    def test_product_delivery_rejects_manifest_tamper(self):
        delivery = build_product_delivery(_bundle(), base_name="x")
        manifest = delivery.files[4]
        altered_bytes = manifest.content_bytes.replace(b'"base_name":"x"', b'"base_name":"y"')
        altered = replace(
            manifest,
            content_bytes=altered_bytes,
            content_sha256=hashlib.sha256(altered_bytes).hexdigest(),
            size_bytes=len(altered_bytes),
        )
        with self.assertRaises(ValueError):
            replace(delivery, files=delivery.files[:4] + (altered,))

    def test_filenames_derive_from_base_and_role(self):
        self.assertEqual(filename_for_role("x", DeliveryRole.HUMAN_REPORT), "x_relatorio.md")


class DeliveryStaticAuditTests(unittest.TestCase):
    def test_runtime_has_no_forbidden_io_clock_random_locale_network_llm(self):
        base = Path(__file__).resolve().parents[1] / "src" / "formatador_academico" / "product_delivery"
        forbidden_import_roots = {
            "os", "pathlib", "socket", "requests", "urllib", "time", "datetime",
            "random", "uuid", "subprocess", "importlib", "locale", "openai", "zipfile",
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

    def test_no_execution_engine_imports(self):
        base = Path(__file__).resolve().parents[1] / "src" / "formatador_academico" / "product_delivery"
        all_source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(base.glob("*.py")))
        for forbidden in ("docx_parser", "analysis.", "classification.engine", "decision.engine", "patcher", "processing_session"):
            self.assertNotIn(forbidden, all_source)


if __name__ == "__main__":
    unittest.main()
