"""Contract tests for the 0060B structural parser stress fixture."""

from __future__ import annotations

import unittest

from formatador_academico.docx_parser import DocxParser, serialize_parse_result

from fixture_0060 import build_structural_stress_package, load_stress_spec


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


class StructuralStressFixture0060Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_stress_spec()
        cls.package = build_structural_stress_package()
        cls.result = DocxParser().parse_bytes(cls.package)

    def test_fixture_declares_every_required_stress_feature(self):
        expected = {
            "same-name siblings interleaved with other nodes",
            "comments and processing instructions",
            "mc:AlternateContent",
            "w:sdt block containers",
            "hyperlinks",
            "fields",
            "nested tables",
            "depth at the parser limit",
            "header and footnote stories",
        }
        self.assertEqual(set(self.spec["features"]), expected)

    def test_fixture_parses_deterministically_with_secondary_stories(self):
        self.assertEqual(self.result["status"], "ok")
        story_types = {story["story_type"] for story in self.result["stories"]}
        self.assertEqual(story_types, set(self.spec["expected_story_types"]))
        second = DocxParser().parse_bytes(self.package)
        self.assertEqual(serialize_parse_result(self.result), serialize_parse_result(second))

    def test_comments_processing_instructions_and_same_name_siblings_have_paths(self):
        paths = [
            record["structural_path"]
            for record in _walk(self.result)
            if isinstance(record.get("structural_path"), str)
        ]
        self.assertTrue(any("comment()" in path for path in paths))
        self.assertTrue(any("processing-instruction()" in path for path in paths))
        run_paths = [path for path in paths if "/w:r[" in path]
        self.assertEqual(len(run_paths), len(set(run_paths)))
        self.assertGreaterEqual(len(run_paths), self.spec["same_name_sibling_runs"])
        tables = [
            record for record in _walk(self.result)
            if record.get("source_type") == "table"
        ]
        self.assertGreaterEqual(len(tables), self.spec["same_name_sibling_tables"])

    def test_depth_limit_is_exercised_without_losing_the_package(self):
        warning_codes = {item["code"] for item in self.result["parse_warnings"]}
        self.assertIn("max_depth_exceeded", warning_codes)
        limited = [
            record
            for record in _walk(self.result)
            if record.get("depth_limited") is True
        ]
        self.assertTrue(limited)
        self.assertTrue(all(record.get("protected") is True for record in limited))


if __name__ == "__main__":
    unittest.main()
