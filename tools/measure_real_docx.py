#!/usr/bin/env python3
"""Measure the public product boundary against DOCX files supplied locally.

The DOCX inputs are never copied, modified, or written. One JSON object is
emitted per input, making the result suitable for a reproducible local run
without adding private documents to the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


DEFAULT_PROFILE = {
    "schema_version": "0.3",
    "profile": {"id": "real-docx-measurement", "version": "1"},
    "rules": {
        "body": {
            "font_size": {"mode": "exact", "value": 12},
            "alignment": {"mode": "exact", "value": "justify"},
            "line_spacing": {"mode": "exact", "value": 1.5},
        }
    },
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", nargs="+", type=Path)
    parser.add_argument(
        "--profile-json",
        type=Path,
        help="optional UTF-8 Profile Input JSON; defaults to a basic academic body profile",
    )
    parser.add_argument(
        "--max-applied-operations",
        type=int,
        default=None,
        help="optional safety cap for exploratory measurements",
    )
    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))

    from formatador_academico.product_input_boundary import build_product_from_inputs

    profile_object = DEFAULT_PROFILE
    if args.profile_json is not None:
        profile_object = json.loads(args.profile_json.read_text(encoding="utf-8"))
    profile_bytes = json.dumps(
        profile_object, ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")

    for path in args.docx:
        started = time.perf_counter()
        result: dict[str, object] = {
            "file": str(path),
            "bytes": path.stat().st_size,
        }
        try:
            package_bytes = path.read_bytes()
            kwargs = {}
            if args.max_applied_operations is not None:
                kwargs["max_applied_operations"] = args.max_applied_operations
            bundle = build_product_from_inputs(package_bytes, profile_bytes, **kwargs)
            summary = bundle.processing_report.summary
            result.update(
                {
                    "status": bundle.session_status.value,
                    "applied": summary.applied_change_count,
                    "review": summary.review_item_count,
                    "unapplied": summary.unapplied_change_count,
                    "classification_items": summary.classification_item_count,
                    "classified": summary.classified_count,
                    "abstained": summary.abstained_count,
                    "not_applicable": summary.not_applicable_count,
                    "warnings": summary.classification_warning_count,
                }
            )
        except Exception as exc:
            result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
