"""Tests for the exact-equivalence oracle fixed by decision 0060A."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path

from formatador_academico.processing_session import process_document

from test_processing_session_v01 import _body_profile, _two_change_pkg


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "oracle_0060.py"
SPEC = importlib.util.spec_from_file_location("oracle_0060", TOOL)
oracle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = oracle
SPEC.loader.exec_module(oracle)

PROFILE_BYTES = (
    b'{"schema_version":"0.1","profile":{"id":"oracle-0060","version":"1"},'
    b'"rules":{"body":{"bold":{"mode":"exact","value":false},'
    b'"font_size":{"mode":"exact","value":12}}}}'
)


class OracleSerialization0060Tests(unittest.TestCase):
    def test_session_envelope_covers_every_frozen_field(self):
        session = process_document(
            _two_change_pkg(),
            _body_profile(),
            max_applied_operations=1,
        )
        payload = json.loads(oracle.serialize_processing_session_result(session))

        self.assertEqual(
            tuple(field.name for field in fields(session)),
            oracle.EXPECTED_SESSION_FIELDS,
        )
        self.assertEqual(
            set(payload),
            {
                "processing_session_version",
                "status",
                "profile_ref",
                "input_package_sha256",
                "output_package_sha256",
                "output_package_bytes_sha256",
                "transforms",
                "final_classifications",
                "final_decisions",
                "findings",
            },
        )
        self.assertEqual(len(payload["transforms"]), 1)
        self.assertTrue(payload["final_classifications"])
        self.assertTrue(payload["final_decisions"])
        self.assertTrue(payload["findings"])

        self.assertEqual(
            set(payload["profile_ref"]),
            {field.name for field in fields(session.profile_ref)},
        )
        self.assertEqual(
            set(payload["transforms"][0]),
            {field.name for field in fields(session.transforms[0])},
        )
        self.assertEqual(
            set(payload["final_classifications"][0]),
            {field.name for field in fields(session.final_classifications[0])},
        )
        self.assertEqual(
            set(payload["final_decisions"][0]),
            {field.name for field in fields(session.final_decisions[0])},
        )

        finding = session.findings[0]
        self.assertEqual(
            tuple(field.name for field in fields(finding)),
            oracle.EXPECTED_FINDING_FIELDS,
        )
        self.assertEqual(
            set(payload["findings"][0]),
            set(oracle.EXPECTED_FINDING_FIELDS),
        )
        self.assertEqual(
            set(payload["findings"][0]["target"]),
            {field.name for field in fields(finding.target)},
        )

    def test_oracle_does_not_import_or_modify_benchmark_0059(self):
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("import benchmark_0059", source)
        self.assertNotIn("from benchmark_0059", source)


class OracleReference0060Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # actions/checkout is shallow by default.  The 0060A contract requires
        # the fixed SHA to be fetched explicitly before the oracle runs.
        if os.environ.get("GITHUB_ACTIONS") == "true":
            completed = subprocess.run(
                ["git", "fetch", "origin", oracle.REFERENCE_COMMIT],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    "CI could not fetch oracle reference "
                    f"{oracle.REFERENCE_COMMIT}: {completed.stderr.strip()}"
                )
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="test-oracle-0060-")
        cls.package_path = Path(cls.temp_dir.name) / "fixture.docx"
        cls.profile_path = Path(cls.temp_dir.name) / "profile.json"
        cls.package_path.write_bytes(_two_change_pkg())
        cls.profile_path.write_bytes(PROFILE_BYTES)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def _observe(self, source_root: Path, seed: str):
        return oracle.run_worker(
            source_root,
            self.package_path,
            self.profile_path,
            base_name="fixture",
            max_applied_operations=1,
            hash_seed=seed,
        )

    def test_missing_reference_fails_without_current_tree_fallback(self):
        missing = "0" * 40
        with self.assertRaisesRegex(
            oracle.ReferenceMaterializationError,
            f"{missing}.*refusing current-tree fallback",
        ):
            with oracle.materialized_reference(ROOT, missing):
                self.fail("an unavailable commit must not yield a reference tree")

    def test_envelope_is_cross_process_deterministic_for_reference_and_candidate(self):
        candidate_a = self._observe(ROOT, "101")
        candidate_b = self._observe(ROOT, "202")
        self.assertEqual(candidate_a, candidate_b)

        with oracle.materialized_reference(ROOT) as reference_root:
            reference_a = self._observe(reference_root, "303")
            reference_b = self._observe(reference_root, "404")
        self.assertEqual(reference_a, reference_b)
        self.assertEqual(reference_a, candidate_a)

    def test_full_comparison_records_fixed_sha_and_matches(self):
        comparison = oracle.compare_against_reference(
            ROOT,
            self.package_path,
            self.profile_path,
            base_name="fixture",
            max_applied_operations=1,
        )
        self.assertTrue(comparison["equal"])
        self.assertEqual(comparison["reference_commit"], oracle.REFERENCE_COMMIT)
        self.assertTrue(comparison["artifact_comparison"]["equal"])
        output = json.dumps(comparison, sort_keys=True)
        self.assertNotIn(str(self.package_path), output)
        self.assertNotIn("<w:", output)

    def test_failure_path_compares_exception_type_and_condition_without_message(self):
        invalid = Path(self.temp_dir.name) / "invalid.docx"
        invalid.write_bytes(b"not-a-docx")
        comparison = oracle.compare_against_reference(
            ROOT,
            invalid,
            self.profile_path,
            base_name="invalid",
        )
        self.assertTrue(comparison["equal"])
        self.assertEqual(comparison["reference"]["outcome"], "error")
        self.assertIn("exception_type", comparison["reference"])
        self.assertIn("exception_message_sha256", comparison["reference"])
        self.assertIsNone(comparison["artifact_comparison"])
        self.assertNotIn("not-a-docx", json.dumps(comparison, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
