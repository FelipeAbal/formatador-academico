"""Safety and lifecycle tests for the per-parse sibling-position index."""

from __future__ import annotations

import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import formatador_academico.docx_parser as parser_module  # noqa: E402
from fixture_0060 import build_structural_stress_package  # noqa: E402
from test_analysis_formatting_v01b_m1 import build_docx  # noqa: E402


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _simple_package(text: str) -> bytes:
    document = (
        f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>'
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    return build_docx(document)


def _partial_story_package() -> bytes:
    document = (
        f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>'
        "<w:p><w:r><w:t>body remains usable</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    return build_docx(
        document,
        extra_parts={"word/header1.xml": b"<malformed"},
        story_rels=[("rHeader", "header", "header1.xml")],
    )


class SiblingIndex0060BTests(unittest.TestCase):
    def test_parent_is_indexed_once_and_element_objects_are_the_keys(self):
        root = etree.fromstring(
            f'<w:root xmlns:w="{W}"><w:p/><!--between--><w:bookmarkStart/>'
            "<w:p/><?probe value?><w:p/></w:root>"
        )
        first, comment, bookmark, second, instruction, third = tuple(root)
        index = parser_module._SiblingIndex()

        self.assertEqual(index.positions(third), (5, 3))
        self.assertEqual(index.positions(first), (0, 1))
        self.assertEqual(index.positions(comment), (1, 1))
        self.assertEqual(index.positions(bookmark), (2, 1))
        self.assertEqual(index.positions(second), (3, 2))
        self.assertEqual(index.positions(instruction), (4, 1))

        self.assertEqual(index.stats["misses"], 1)
        self.assertEqual(index.stats["hits"], 5)
        self.assertEqual(index.stats["indexed_parents"], 1)
        self.assertEqual(index.stats["indexed_nodes"], 6)
        self.assertIs(next(iter(index._parents)), root)
        self.assertTrue(any(key is third for key in index._parents[root]))

    def test_discard_clears_live_references_and_rejects_reuse(self):
        root = etree.fromstring(f'<w:root xmlns:w="{W}"><w:p/></w:root>')
        child = root[0]
        index = parser_module._SiblingIndex()
        index.positions(child)
        index.discard()

        self.assertEqual(index.stats["invalidations"], 1)
        self.assertEqual(index.stats["active_parents"], 0)
        with self.assertRaisesRegex(RuntimeError, "already discarded"):
            index.positions(child)

    def test_parse_discards_index_after_success_and_any_failure(self):
        created = []
        real_index = parser_module._SiblingIndex

        def create_index():
            instance = real_index()
            created.append(instance)
            return instance

        with patch.object(parser_module, "_SiblingIndex", side_effect=create_index):
            success = parser_module.DocxParser().parse_bytes(_simple_package("ok"))
            failure = parser_module.DocxParser().parse_bytes(b"not-a-docx")
            with patch.object(
                parser_module,
                "_safe_zip_inventory",
                side_effect=RuntimeError("unexpected test failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "unexpected test failure"):
                    parser_module.DocxParser().parse_bytes(_simple_package("boom"))

        self.assertEqual(success["status"], "ok")
        self.assertEqual(failure["status"], "failed")
        self.assertEqual(len(created), 3)
        for index in created:
            self.assertEqual(index.stats["invalidations"], 1)
            self.assertEqual(index.stats["active_parents"], 0)

    def test_successive_a_b_a_parses_do_not_share_state(self):
        parser = parser_module.DocxParser()
        package_a = build_structural_stress_package()
        package_b = _simple_package("different document")

        first_a = parser_module.serialize_parse_result(parser.parse_bytes(package_a))
        result_b = parser_module.serialize_parse_result(parser.parse_bytes(package_b))
        second_a = parser_module.serialize_parse_result(parser.parse_bytes(package_a))

        self.assertEqual(first_a, second_a)
        self.assertNotEqual(first_a, result_b)

    def test_same_parser_is_deterministic_under_concurrent_threads(self):
        parser = parser_module.DocxParser()
        packages = [build_structural_stress_package(), _simple_package("thread-b")]
        expected = [
            parser_module.serialize_parse_result(parser.parse_bytes(package))
            for package in packages
        ]

        def parse(index: int) -> tuple[int, bytes]:
            package_index = index % len(packages)
            result = parser.parse_bytes(packages[package_index])
            return package_index, parser_module.serialize_parse_result(result)

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(parse, range(12)))

        for package_index, serialized in results:
            self.assertEqual(serialized, expected[package_index])

    def test_partial_story_remains_partial_and_deterministic(self):
        package = _partial_story_package()
        parser = parser_module.DocxParser()
        first = parser.parse_bytes(package)
        second = parser.parse_bytes(package)

        self.assertEqual(first["status"], "partial")
        self.assertEqual(first["stories"][0]["status"], "ok")
        self.assertEqual(first["stories"][1]["status"], "failed")
        self.assertEqual(
            parser_module.serialize_parse_result(first),
            parser_module.serialize_parse_result(second),
        )

    def test_parser_version_remains_frozen(self):
        self.assertEqual(parser_module.PARSER_VERSION, "0.4.0")


if __name__ == "__main__":
    unittest.main()
