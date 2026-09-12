"""Verifies the compact WML fixture used by the formatting-slice audit."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from lxml import etree

from formatador_academico.patcher.xml_patch import PPR_CANONICAL_ORDER

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class WmlFormattingSliceFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parent / "fixtures" / "wml-formatting-slice-v01.json"
        cls.fixture = json.loads(path.read_text(encoding="utf-8"))

    def test_fixture_declares_exact_target_property_units(self):
        actual = {
            (item["target_type"], item["target_class"], item["property_slot"])
            for item in self.fixture["cases"]
        }
        self.assertEqual(actual, {
            ("run", "body", "font_size"),
            ("run", "body", "bold"),
            ("paragraph", "body", "alignment"),
            ("paragraph", "body", "spacing.line"),
        })

    def test_fixture_fragments_are_well_formed_wml(self):
        for item in self.fixture["cases"]:
            root = etree.fromstring(item["xml"].encode("utf-8"))
            self.assertEqual(etree.QName(root).namespace, W_NS)
            self.assertEqual(etree.QName(root).localname, item["target_type"][:1] == "r" and "r" or "p")

    def test_fixture_covers_complete_ppr_order(self):
        self.assertEqual(tuple(self.fixture["canonical_ppr_order"]), PPR_CANONICAL_ORDER)


if __name__ == "__main__":
    unittest.main()
