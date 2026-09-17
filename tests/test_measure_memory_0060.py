"""Tests for the cycle-0060 memory measurement instrument."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_processing_session_v01 import _two_change_pkg


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "measure_memory_0060.py"
SPEC = importlib.util.spec_from_file_location("measure_memory_0060", TOOL)
memory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = memory
SPEC.loader.exec_module(memory)

PROFILE_BYTES = (
    b'{"schema_version":"0.1","profile":{"id":"memory-0060","version":"1"},'
    b'"rules":{"body":{"bold":{"mode":"exact","value":false}}}}'
)


class DeepSize0060Tests(unittest.TestCase):
    def test_shared_object_is_counted_once(self):
        shared = bytearray(b"x" * 1024)
        aliased = memory.deep_size_bytes([shared, shared])
        distinct = memory.deep_size_bytes(
            [bytearray(b"x" * 1024), bytearray(b"x" * 1024)]
        )
        self.assertLess(aliased, distinct)

    def test_cycle_does_not_recurse_forever(self):
        cyclic = []
        cyclic.append(cyclic)
        self.assertGreater(memory.deep_size_bytes(cyclic), 0)


class MemoryInstrument0060Tests(unittest.TestCase):
    def test_synthetic_document_records_only_name_size_hash_and_memory(self):
        with tempfile.TemporaryDirectory(prefix="memory-0060-") as temp_dir:
            package = Path(temp_dir) / "synthetic.docx"
            profile = Path(temp_dir) / "profile.json"
            package.write_bytes(_two_change_pkg())
            profile.write_bytes(PROFILE_BYTES)

            result = memory.measure_document(ROOT, package, profile)

        self.assertEqual(result["schema_version"], memory.SCHEMA_VERSION)
        self.assertEqual(result["input"]["name"], "synthetic.docx")
        self.assertGreater(result["input"]["size_bytes"], 0)
        self.assertEqual(len(result["input"]["sha256"]), 64)
        self.assertGreater(result["ir"]["deep_size_bytes"], 0)
        self.assertGreater(result["parse_peak"]["tracemalloc_bytes"], 0)
        self.assertGreater(result["parse_peak"]["process_rss_bytes"], 0)
        self.assertGreater(result["pipeline_peak"]["tracemalloc_bytes"], 0)
        self.assertGreater(result["pipeline_peak"]["process_rss_bytes"], 0)
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn(temp_dir, encoded)
        self.assertNotIn("<w:", encoded)

    def test_tool_is_separate_from_benchmark_0059(self):
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("benchmark_0059", source)


if __name__ == "__main__":
    unittest.main()
