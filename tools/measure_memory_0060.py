#!/usr/bin/env python3
"""Measure PhysicalIR size and isolated process peak memory for cycle 0060."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import resource
import subprocess
import sys
import tracemalloc
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = "0060.1"


class MemoryMeasurementError(RuntimeError):
    pass


def deep_size_bytes(value: object) -> int:
    """Return recursive Python heap size, counting shared objects once."""

    seen: set[int] = set()

    def visit(item: object) -> int:
        identity = id(item)
        if identity in seen:
            return 0
        seen.add(identity)
        size = sys.getsizeof(item)
        if isinstance(item, dict):
            size += sum(visit(key) + visit(child) for key, child in item.items())
        elif isinstance(item, (tuple, list, set, frozenset)):
            size += sum(visit(child) for child in item)
        elif is_dataclass(item) and not isinstance(item, type):
            size += sum(visit(getattr(item, field.name)) for field in fields(item))
        return size

    return visit(value)


def _rss_peak_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB; macOS and the BSDs report bytes.
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _metadata(package_path: Path, package_bytes: bytes) -> dict[str, Any]:
    return {
        "name": package_path.name,
        "size_bytes": len(package_bytes),
        "sha256": hashlib.sha256(package_bytes).hexdigest(),
    }


def _measure_parse(package_path: Path) -> dict[str, Any]:
    from formatador_academico.docx_parser import DocxParser, serialize_parse_result

    package_bytes = package_path.read_bytes()
    gc.collect()
    tracemalloc.start()
    ir = DocxParser().parse_bytes(package_bytes)
    current, peak = tracemalloc.get_traced_memory()
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "parse",
        "input": _metadata(package_path, package_bytes),
        "ir_deep_size_bytes": deep_size_bytes(ir),
        "ir_serialized_size_bytes": len(serialize_parse_result(ir)),
        "ir_serialized_sha256": hashlib.sha256(serialize_parse_result(ir)).hexdigest(),
        "tracemalloc_current_bytes": current,
        "tracemalloc_peak_bytes": peak,
        "process_rss_peak_bytes": _rss_peak_bytes(),
    }
    tracemalloc.stop()
    return result


def _measure_pipeline(package_path: Path, profile_path: Path) -> dict[str, Any]:
    from formatador_academico.product_delivery import build_product_delivery
    from formatador_academico.product_input_boundary import build_product_from_inputs

    package_bytes = package_path.read_bytes()
    profile_bytes = profile_path.read_bytes()
    gc.collect()
    tracemalloc.start()
    bundle = build_product_from_inputs(package_bytes, profile_bytes)
    delivery = build_product_delivery(bundle, base_name="memory-0060")
    current, peak = tracemalloc.get_traced_memory()
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "pipeline",
        "input": _metadata(package_path, package_bytes),
        "session_status": bundle.session_status.value,
        "delivery_sha256": [item.content_sha256 for item in delivery.files],
        "tracemalloc_current_bytes": current,
        "tracemalloc_peak_bytes": peak,
        "process_rss_peak_bytes": _rss_peak_bytes(),
    }
    tracemalloc.stop()
    return result


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _run_worker(
    source_root: Path,
    mode: str,
    package_path: Path,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(source_root.resolve() / "src")
        + os.pathsep
        + env.get("PYTHONPATH", "")
    )
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_worker",
        "--source-root",
        str(source_root),
        "--mode",
        mode,
        "--docx",
        str(package_path),
    ]
    if profile_path is not None:
        command.extend(("--profile", str(profile_path)))
    completed = subprocess.run(
        command,
        cwd=source_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise MemoryMeasurementError(f"{mode} worker failed: {detail}")
    try:
        return json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MemoryMeasurementError(f"{mode} worker returned invalid JSON") from exc


def measure_document(
    source_root: Path,
    package_path: Path,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    parse = _run_worker(source_root, "parse", package_path)
    pipeline = (
        _run_worker(source_root, "pipeline", package_path, profile_path)
        if profile_path is not None
        else None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "input": parse["input"],
        "ir": {
            "deep_size_bytes": parse["ir_deep_size_bytes"],
            "serialized_size_bytes": parse["ir_serialized_size_bytes"],
            "serialized_sha256": parse["ir_serialized_sha256"],
        },
        "parse_peak": {
            "tracemalloc_bytes": parse["tracemalloc_peak_bytes"],
            "process_rss_bytes": parse["process_rss_peak_bytes"],
        },
        "pipeline_peak": (
            {
                "tracemalloc_bytes": pipeline["tracemalloc_peak_bytes"],
                "process_rss_bytes": pipeline["process_rss_peak_bytes"],
                "session_status": pipeline["session_status"],
                "delivery_sha256": pipeline["delivery_sha256"],
            }
            if pipeline is not None
            else None
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    measure = subparsers.add_parser("measure")
    measure.add_argument("--source-root", type=Path, default=Path.cwd())
    measure.add_argument("--docx", type=Path, required=True)
    measure.add_argument("--profile", type=Path)
    measure.add_argument("--output", type=Path)

    worker = subparsers.add_parser("_worker")
    worker.add_argument("--source-root", type=Path, required=True)
    worker.add_argument("--mode", choices=("parse", "pipeline"), required=True)
    worker.add_argument("--docx", type=Path, required=True)
    worker.add_argument("--profile", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source_root = args.source_root.resolve()
        sys.path.insert(0, str(source_root / "src"))
        if args.command == "_worker":
            if args.mode == "pipeline" and args.profile is None:
                raise MemoryMeasurementError("pipeline mode requires --profile")
            result = (
                _measure_parse(args.docx)
                if args.mode == "parse"
                else _measure_pipeline(args.docx, args.profile)
            )
        else:
            result = measure_document(
                source_root,
                args.docx.resolve(),
                args.profile.resolve() if args.profile else None,
            )
        encoded = _canonical_json_bytes(result)
        if args.command == "measure" and args.output is not None:
            args.output.write_bytes(encoded + b"\n")
        else:
            print(encoded.decode("utf-8"))
        return 0
    except MemoryMeasurementError as exc:
        print(f"measure_memory_0060: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
