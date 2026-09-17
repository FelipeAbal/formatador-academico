"""Tests for the exact-equivalence oracle fixed by decision 0060A."""

from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from formatador_academico.processing_session import process_document

from test_processing_session_v01 import _body_profile, _two_change_pkg
from fixture_0060 import build_structural_stress_package


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

    def test_instrument_error_is_never_converted_to_application_error(self):
        with mock.patch.object(
            oracle,
            "build_observation",
            side_effect=oracle.OracleError("symmetric instrument defect"),
        ):
            with self.assertRaisesRegex(oracle.OracleError, "instrument defect"):
                oracle.build_observation_or_error(
                    b"package",
                    b"profile",
                    base_name="fixture",
                    max_applied_operations=1,
                )

    def test_cross_run_binding_checks_all_product_lineage(self):
        cases = (
            ("clean_package_sha256", "binding_clean_sha"),
            ("session_status", "binding_status"),
            ("profile_ref", "binding_profile"),
            ("input_package_sha256", "binding_input_sha"),
            ("processing_report_ref", "binding_report_ref"),
            ("review_package_sha256", "binding_review_sha"),
        )
        for field_name, expected_code in cases:
            with self.subTest(field=field_name):
                session = SimpleNamespace(
                    output_package_sha256="a",
                    status=object(),
                    profile_ref=object(),
                    input_package_sha256="b",
                )
                bundle = SimpleNamespace(
                    clean_package_sha256="a",
                    session_status=session.status,
                    profile_ref=session.profile_ref,
                    input_package_sha256="b",
                    processing_report_ref="c",
                    review_package_sha256="d",
                )
                oracle._assert_execution_binding(
                    session,
                    bundle,
                    session_report_ref="c",
                    session_review_sha256="d",
                )
                setattr(bundle, field_name, object())
                with self.assertRaises(oracle.OracleError) as raised:
                    oracle._assert_execution_binding(
                        session,
                        bundle,
                        session_report_ref="c",
                        session_review_sha256="d",
                    )
                self.assertEqual(raised.exception.code, expected_code)

    def test_namespace_package_reports_stable_code_without_path(self):
        with tempfile.TemporaryDirectory(prefix="oracle-namespace-") as temp_dir:
            root = Path(temp_dir)
            (root / "src" / "formatador_academico").mkdir(parents=True)
            package = root / "input.docx"
            profile = root / "profile.json"
            package.write_bytes(b"unused")
            profile.write_bytes(b"unused")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "_worker",
                    "--source-root",
                    str(root),
                    "--package",
                    str(package),
                    "--profile",
                    str(profile),
                    "--base-name",
                    "namespace",
                    "--max-applied-operations",
                    "1",
                ],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertIn("code=source_package_namespace", combined)
        self.assertNotIn(temp_dir, combined)

    def test_worker_preserves_only_known_diagnostic_code(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout=b"",
            stderr=(
                b"oracle_0060: instrument_error; code=binding_report_ref; "
                b"type=OracleError; detail_sha256=abc\n"
            ),
        )
        with mock.patch.object(oracle.subprocess, "run", return_value=completed):
            with self.assertRaises(oracle.WorkerError) as raised:
                oracle.run_worker(
                    ROOT,
                    Path("input.docx"),
                    Path("profile.json"),
                    base_name="fixture",
                    max_applied_operations=1,
                )
        self.assertEqual(raised.exception.code, "binding_report_ref")

        completed.stderr = (
            b"oracle_0060: instrument_error; code=private-path-content; "
            b"type=OracleError\n"
        )
        with mock.patch.object(oracle.subprocess, "run", return_value=completed):
            with self.assertRaises(oracle.WorkerError) as rejected:
                oracle.run_worker(
                    ROOT,
                    Path("input.docx"),
                    Path("profile.json"),
                    base_name="fixture",
                    max_applied_operations=1,
                )
        self.assertEqual(rejected.exception.code, "worker_exit")


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
                    f"{oracle.REFERENCE_COMMIT}; "
                    f"stderr_sha256={oracle._sha(completed.stderr.encode('utf-8'))}"
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
        self.assertEqual(comparison["outcome"], "success")
        self.assertEqual(comparison["reference_commit"], oracle.REFERENCE_COMMIT)
        self.assertTrue(comparison["artifact_comparison"]["equal"])
        output = json.dumps(comparison, sort_keys=True)
        self.assertNotIn(str(self.package_path), output)
        self.assertNotIn("<w:", output)

    def test_failure_path_requires_explicit_error_equivalence_opt_in(self):
        invalid = Path(self.temp_dir.name) / "invalid.docx"
        invalid.write_bytes(b"not-a-docx")
        comparison = oracle.compare_against_reference(
            ROOT,
            invalid,
            self.profile_path,
            base_name="invalid",
        )
        self.assertFalse(comparison["equal"])
        self.assertEqual(comparison["outcome"], "both_error")
        self.assertEqual(comparison["reference"]["outcome"], "error")
        self.assertIn("exception_type", comparison["reference"])
        self.assertIn("exception_message_sha256", comparison["reference"])
        self.assertIsNone(comparison["artifact_comparison"])
        self.assertNotIn("not-a-docx", json.dumps(comparison, sort_keys=True))

        allowed = oracle.compare_against_reference(
            ROOT,
            invalid,
            self.profile_path,
            base_name="invalid",
            allow_error_equivalence=True,
        )
        self.assertTrue(allowed["equal"])
        self.assertEqual(allowed["outcome"], "both_error")

        cli = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "compare",
                "--repo-root",
                str(ROOT),
                "--package",
                str(invalid),
                "--profile",
                str(self.profile_path),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(cli.returncode, 3)
        self.assertFalse(json.loads(cli.stdout)["equal"])

    def test_comparison_rejects_every_divergence_branch(self):
        baseline = self._observe(ROOT, "505")

        @contextmanager
        def fake_reference(_repo_root):
            yield ROOT

        cases = []
        non_artifact = deepcopy(baseline)
        non_artifact["parse_result_sha256"] = "0" * 64
        cases.append((baseline, non_artifact))

        artifact = deepcopy(baseline)
        artifact["artifacts"][0]["sha256"] = "0" * 64
        cases.append((baseline, artifact))

        application_error = {
            "outcome": "error",
            "exception_type": "builtins.ValueError",
            "exception_message_sha256": "0" * 64,
        }
        cases.append((baseline, application_error))

        for reference, candidate in cases:
            with self.subTest(candidate=candidate.get("outcome")):
                with mock.patch.object(
                    oracle, "materialized_reference", fake_reference
                ), mock.patch.object(
                    oracle, "run_worker", side_effect=[reference, candidate]
                ):
                    comparison = oracle.compare_against_reference(
                        ROOT,
                        self.package_path,
                        self.profile_path,
                    )
                self.assertFalse(comparison["equal"])

    def test_infrastructure_failure_never_emits_absolute_paths(self):
        private_input = Path(self.temp_dir.name) / "private-document.docx"
        private_input.mkdir()
        completed = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "compare",
                "--repo-root",
                str(ROOT),
                "--package",
                str(private_input),
                "--profile",
                str(self.profile_path),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertNotIn(str(private_input), combined)
        self.assertNotIn(str(ROOT), combined)

    def test_mutated_instrument_cannot_report_equivalence(self):
        mutant_dir = Path(self.temp_dir.name) / "mutant-tools"
        mutant_dir.mkdir()
        mutant = mutant_dir / "oracle_0060.py"
        comparator = mutant_dir / "artifact_comparator_0060.py"
        source = TOOL.read_text(encoding="utf-8")
        marker = '    """Run the frozen public pipeline and emit hashes only."""\n'
        self.assertIn(marker, source)
        mutant.write_text(
            source.replace(
                marker,
                marker + '\n    raise OracleError("symmetric instrument defect")\n',
                1,
            ),
            encoding="utf-8",
        )
        shutil.copy2(ROOT / "tools" / "artifact_comparator_0060.py", comparator)

        completed = subprocess.run(
            [
                sys.executable,
                str(mutant),
                "compare",
                "--repo-root",
                str(ROOT),
                "--package",
                str(self.package_path),
                "--profile",
                str(self.profile_path),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertNotIn('"equal":true', combined)
        self.assertNotIn(str(mutant), combined)
        self.assertNotIn(str(self.package_path), combined)

    def test_stale_comparator_bytecode_is_ignored(self):
        mutant_dir = Path(self.temp_dir.name) / "stale-pyc-tools"
        mutant_dir.mkdir()
        mutant_oracle = mutant_dir / "oracle_0060.py"
        mutant_comparator = mutant_dir / "artifact_comparator_0060.py"
        shutil.copy2(TOOL, mutant_oracle)
        original = (ROOT / "tools" / "artifact_comparator_0060.py").read_text(
            encoding="utf-8"
        )
        marker = '    "clean_docx",\n    "review_docx",\n'
        poisoned = original.replace(
            marker,
            '    "review_docx",\n    "clean_docx",\n',
            1,
        )
        self.assertNotEqual(original, poisoned)
        self.assertEqual(len(original.encode("utf-8")), len(poisoned.encode("utf-8")))

        timestamp = 1_700_000_000
        mutant_comparator.write_text(poisoned, encoding="utf-8")
        os.utime(mutant_comparator, (timestamp, timestamp))
        py_compile.compile(
            str(mutant_comparator),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP,
        )
        mutant_comparator.write_text(original, encoding="utf-8")
        os.utime(mutant_comparator, (timestamp, timestamp))

        completed = subprocess.run(
            [
                sys.executable,
                str(mutant_oracle),
                "compare",
                "--repo-root",
                str(ROOT),
                "--package",
                str(self.package_path),
                "--profile",
                str(self.profile_path),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["equal"])

    def test_structural_stress_fixture_passes_through_oracle(self):
        stress = Path(self.temp_dir.name) / "structural-stress.docx"
        stress.write_bytes(build_structural_stress_package())
        comparison = oracle.compare_against_reference(
            ROOT,
            stress,
            self.profile_path,
            base_name="structural-stress",
            max_applied_operations=1,
        )
        self.assertTrue(comparison["equal"])
        self.assertEqual(
            comparison["reference"]["parse_result_sha256"],
            comparison["candidate"]["parse_result_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
