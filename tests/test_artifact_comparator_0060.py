"""Tests for the cycle-0060 artifact hash comparator."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from formatador_academico.product_delivery import ROLE_ORDER as PRODUCT_ROLE_ORDER


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "artifact_comparator_0060.py"
SPEC = importlib.util.spec_from_file_location("artifact_comparator_0060", TOOL)
comparator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = comparator
SPEC.loader.exec_module(comparator)


def _records(*, changed_role: str | None = None):
    records = []
    for role in comparator.ROLE_ORDER:
        content = bytearray(role.encode())
        if role == changed_role:
            content[-1] ^= 1
        records.append(
            comparator.digest_bytes(role, f"fixture-{role}.bin", bytes(content))
        )
    return tuple(records)


class ArtifactComparator0060Tests(unittest.TestCase):
    def test_role_order_matches_frozen_product_delivery(self):
        self.assertEqual(
            comparator.ROLE_ORDER,
            tuple(role.value for role in PRODUCT_ROLE_ORDER),
        )

    def test_equal_artifacts_compare_equal(self):
        records = _records()
        result = comparator.compare_artifacts(
            records,
            records,
            reference_commit="4" * 40,
        )
        self.assertTrue(result.equal)
        self.assertEqual(result.mismatches, ())

    def test_one_byte_difference_is_reported_by_hash_and_size_only(self):
        reference = _records()
        candidate = _records(changed_role="review_docx")
        result = comparator.compare_artifacts(
            reference,
            candidate,
            reference_commit="4" * 40,
        )
        self.assertFalse(result.equal)
        self.assertEqual(result.mismatches[0].role, "review_docx")
        self.assertEqual(result.mismatches[0].fields, ("sha256",))

        output = comparator.comparison_json_bytes(result)
        payload = json.loads(output)
        self.assertNotIn("content", output.decode("utf-8").lower())
        self.assertNotIn(str(ROOT), output.decode("utf-8"))
        self.assertEqual(payload["reference_commit"], "4" * 40)

    def test_role_order_is_mandatory(self):
        records = list(_records())
        records[0], records[1] = records[1], records[0]
        with self.assertRaisesRegex(ValueError, "ROLE_ORDER"):
            comparator.compare_artifacts(
                records,
                _records(),
                reference_commit="4" * 40,
            )

    def test_manifest_rejects_paths_and_abbreviated_reference(self):
        with self.assertRaisesRegex(ValueError, "basename"):
            comparator.digest_bytes("clean_docx", "folder/file.docx", b"x")
        with self.assertRaisesRegex(ValueError, "basename"):
            comparator.digest_bytes("clean_docx", "folder\\file.docx", b"x")
        with self.assertRaisesRegex(ValueError, "full lowercase Git SHA"):
            comparator.compare_artifacts(
                _records(),
                _records(),
                reference_commit="4bcda30",
            )


if __name__ == "__main__":
    unittest.main()
