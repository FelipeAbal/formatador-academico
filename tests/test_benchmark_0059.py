"""Tests for tools/benchmark_0059.py (cycle 0059 benchmark instrument).

These tests exercise the measuring instrument, not production code. They use
tiny fixtures so they stay fast, and a test-only hold hook to make timeout
behaviour deterministic.
"""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "benchmark_0059.py"
_SPEC = importlib.util.spec_from_file_location("benchmark_0059", TOOL)
bench = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bench)

TINY = (6, 2)
RUN_TIMEOUT = 180.0
HOLD_TIMEOUT = 10.0


class FixtureTests(unittest.TestCase):
    def test_fixture_bytes_are_deterministic_and_stored(self):
        first = bench.make_docx(12, 3)
        self.assertEqual(first, bench.make_docx(12, 3))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            infos = archive.infolist()
        self.assertTrue(infos)
        self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in infos))
        self.assertTrue(all(info.date_time == bench.FIXED_DATE for info in infos))

    def test_fixture_shape_is_counted_by_the_real_parser(self):
        self.assertEqual(bench._ir_counts(bench.make_docx(12, 3)), (12, 12))


class PureFunctionTests(unittest.TestCase):
    def test_schedule_is_fixed_and_balanced(self):
        self.assertEqual(bench.schedule(1), ["reference", "instrumented"])
        self.assertEqual(
            bench.schedule(2),
            ["reference", "instrumented", "instrumented", "reference"],
        )
        three = bench.schedule(3)
        self.assertEqual(three, bench.schedule(3))
        self.assertEqual(three.count("reference"), 3)
        self.assertEqual(three.count("instrumented"), 3)

    def test_exclusive_seconds_subtract_measured_children(self):
        inclusive = {
            "decision": 5.0, "formatting_resolution": 3.0,
            "patch_total": 10.0, "xml_mutation": 1.0, "zip_repackaging": 1.0,
            "allowed_delta_validation": 2.0, "postcondition": 4.0,
            "postcondition_parse": 1.5, "postcondition_style_catalog": 0.5,
            "postcondition_target_resolution": 0.5,
            "postcondition_formatting_resolution": 1.0,
        }
        exclusive = bench.exclusive_seconds(inclusive)
        self.assertAlmostEqual(exclusive["decision"], 2.0)
        self.assertAlmostEqual(exclusive["patch_total"], 2.0)
        self.assertAlmostEqual(exclusive["postcondition"], 0.5)

    def test_timing_semantics_declare_the_official_total_and_hierarchy(self):
        semantics = bench.TIMING_SEMANTICS
        self.assertEqual(semantics["official_total_variant"], "reference")
        self.assertEqual(set(semantics["hierarchy"]), set(bench.STAGE_HIERARCHY))

    def test_json_value_serialises_decimal_bearing_values(self):
        from formatador_academico.decision.model import LineSpacingValue
        from decimal import Decimal

        value = bench._json_value(LineSpacingValue("auto", Decimal("1.5"), "multiple"))
        self.assertEqual(value, {"rule": "auto", "value": "1.5", "unit": "multiple"})
        json.dumps(value)

    def test_academic_profile_is_accepted_by_the_real_boundary(self):
        from formatador_academico.profile_input import parse_profile_input_json

        profile = parse_profile_input_json(bench.ACADEMIC_PROFILE_BYTES)
        self.assertEqual(
            sorted((rule.target_class, rule.property_name) for rule in profile.rules),
            [("body", "alignment"), ("body", "font_size"), ("body", "line_spacing")],
        )


class WorkerRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = bench.run_case(TOOL, *TINY, RUN_TIMEOUT, False)
        cls.instrumented = bench.run_case(TOOL, *TINY, RUN_TIMEOUT, True)

    def test_runs_complete_with_the_expected_clean_changes(self):
        for record in (self.reference, self.instrumented):
            with self.subTest(variant=record.get("variant")):
                self.assertTrue(record["complete"])
                self.assertEqual(record["applied_changes"], TINY[1])
                self.assertEqual(record["session_status"], "quiescent")
                self.assertEqual(record["outcome"], "quiescent")
                self.assertEqual(record["review_items"], 0)
                self.assertEqual(record["unapplied_changes"], 0)

    def test_instrumentation_does_not_change_outputs(self):
        self.assertEqual(bench._equivalence(self.reference), bench._equivalence(self.instrumented))

    def test_reference_has_no_stage_timers(self):
        self.assertEqual(self.reference["variant"], "reference")
        self.assertEqual(self.reference["stage_seconds"], {})
        self.assertIsNone(self.reference["postcondition_share_of_patch_total"])

    def test_postcondition_parse_is_measured_and_not_counted_as_evaluation_parse(self):
        changes = TINY[1]
        calls = self.instrumented["stage_calls"]
        seconds = self.instrumented["stage_seconds"]
        self.assertEqual(calls["postcondition"], changes)
        self.assertEqual(calls["postcondition_parse"], changes)
        self.assertEqual(calls["postcondition_style_catalog"], changes)
        self.assertEqual(calls["parse"], changes + 1)
        self.assertGreater(seconds["postcondition_parse"], 0.0)
        self.assertLessEqual(seconds["postcondition_parse"], seconds["postcondition"])
        exclusive = self.instrumented["stage_seconds_exclusive"]
        for parent in ("decision", "patch_total", "postcondition"):
            self.assertGreaterEqual(exclusive[parent], -1e-6)
        share = self.instrumented["postcondition_share_of_patch_total"]
        self.assertGreater(share, 0.0)
        self.assertLessEqual(share, 1.0)

    def test_progress_writes_stay_at_coarse_boundaries_and_match_across_variants(self):
        changes = TINY[1]
        evaluations = changes + 1
        bound = 2 * evaluations + changes + 10
        for record in (self.reference, self.instrumented):
            with self.subTest(variant=record.get("variant")):
                self.assertGreater(record["progress_writes"], 0)
                self.assertLessEqual(record["progress_writes"], bound)
        self.assertEqual(self.reference["progress_writes"], self.instrumented["progress_writes"])

    def test_timestamps_are_recorded(self):
        for record in (self.reference, self.instrumented):
            self.assertLessEqual(record["started_at"], record["finished_at"])


class TimeoutTests(unittest.TestCase):
    def _run_held(self, instrumented: bool):
        with mock.patch.dict(os.environ, {bench.TEST_HOLD_ENV: "evaluation"}):
            return bench.run_case(TOOL, *TINY, HOLD_TIMEOUT, instrumented)

    def _assert_diagnostic(self, record):
        self.assertFalse(record["complete"])
        self.assertEqual(record["outcome"], "timeout")
        self.assertEqual(record["last_completed_stage"], "evaluation")
        self.assertEqual(record["evaluations_started"], 1)
        self.assertEqual(record["applied_changes"], 0)
        self.assertEqual(record["paragraphs"], TINY[0])

    def test_reference_timeout_keeps_progress(self):
        self._assert_diagnostic(self._run_held(False))

    def test_instrumented_timeout_keeps_progress(self):
        self._assert_diagnostic(self._run_held(True))


class InterleavedSuiteTests(unittest.TestCase):
    def test_suite_interleaves_variants_and_records_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "suite.json"
            args = Namespace(only=None, repeats=2, timeout=RUN_TIMEOUT, output=output)
            result = bench.run_suite(args, case_list=[("T1", *TINY)])
            written = json.loads(output.read_text(encoding="utf-8"))
        case = result["cases"][0]
        self.assertEqual([run["variant"] for run in case["runs"]], bench.schedule(2))
        self.assertEqual([run["sequence"] for run in case["runs"]], [1, 2, 3, 4])
        self.assertEqual([run["case_position"] for run in case["runs"]], [1, 2, 3, 4])
        self.assertFalse(case["stopped_early"])
        for run in case["runs"]:
            self.assertTrue(run["complete"])
            self.assertLessEqual(run["started_at"], run["finished_at"])
        stats = case["statistics"]
        self.assertEqual(stats["official_total_variant"], "reference")
        self.assertEqual(stats["reference"]["complete_runs"], 2)
        self.assertEqual(stats["instrumented"]["complete_runs"], 2)
        self.assertIn("postcondition_share_of_patch_total", stats["instrumented"])
        self.assertIn("instrumentation_overhead_median_seconds", stats)
        self.assertEqual(written["mode"], "synthetic")
        self.assertEqual(written["timing_semantics"]["official_total_variant"], "reference")


class DocxModeTests(unittest.TestCase):
    def _git_status(self):
        if shutil.which("git") is None:
            self.skipTest("git is not available")
        return subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=str(ROOT), capture_output=True, text=True, check=True,
        ).stdout

    def _run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(TOOL), *arguments],
            cwd=str(ROOT), capture_output=True, text=True, timeout=900,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        )

    def test_docx_mode_measures_a_file_in_place_without_copying_it(self):
        status_before = self._git_status()
        data = bench.make_docx(*TINY)
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "privado-exemplo.docx"
            docx.write_bytes(data)
            profile = Path(tmp) / "perfil.json"
            profile.write_bytes(bench.profile_bytes())
            output = Path(tmp) / "docx.json"
            completed = self._run_cli(
                "--docx", str(docx), "--profile", str(profile),
                "--repeats", "1", "--timeout", str(RUN_TIMEOUT), "--output", str(output),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
            text = output.read_text(encoding="utf-8")
            self.assertEqual(docx.read_bytes(), data)
            temporary_directory = tmp
        self.assertEqual(status_before, self._git_status())
        result = json.loads(text)
        self.assertEqual(result["mode"], "docx")
        self.assertEqual(result["profile_source"], "file")
        document = result["documents"][0]
        self.assertEqual(document["label"], "privado-exemplo.docx")
        self.assertEqual(document["input_bytes"], len(data))
        self.assertNotIn("path", document)
        self.assertEqual([run["variant"] for run in document["runs"]], bench.schedule(1))
        for run in document["runs"]:
            self.assertTrue(run["complete"])
            self.assertEqual(run["outcome"], "quiescent")
            self.assertEqual(run["applied_changes"], TINY[1])
            self.assertTrue(run["input_unchanged_on_disk"])
            self.assertTrue(run["input_unchanged_in_memory"])
            self.assertNotIn("path", run)
        self.assertNotIn(temporary_directory, text)
        self.assertNotIn(base64.b64encode(data[:120]).decode("ascii"), text)
        self.assertNotIn("deterministic benchmark text", text)

    def test_docx_mode_records_errors_without_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "nao-e-docx.docx"
            broken.write_bytes(b"not a zip package")
            output = Path(tmp) / "erro.json"
            completed = self._run_cli(
                "--docx", str(broken), "--repeats", "1",
                "--timeout", str(RUN_TIMEOUT), "--output", str(output),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
            result = json.loads(output.read_text(encoding="utf-8"))
        document = result["documents"][0]
        self.assertEqual(result["profile_source"], "builtin-academic-0059")
        self.assertTrue(document["runs"])
        first = document["runs"][0]
        self.assertFalse(first["complete"])
        self.assertEqual(first["outcome"], "error")
        self.assertIn("error_type", first)
        self.assertNotIn("error_message", first)
        self.assertLessEqual(len(document["runs"]), 2)


if __name__ == "__main__":
    unittest.main()
