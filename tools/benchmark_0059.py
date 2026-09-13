#!/usr/bin/env python3
"""Reproducible Cycle 0059 benchmark.

The worker always uses ``build_product_from_inputs`` and, for the end-to-end
number, ``build_product_delivery``. Instrumentation is installed only in the
worker process and wraps names already imported by the frozen processing loop.
No production module is edited by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def _part(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
    info.compress_type = zipfile.ZIP_STORED
    zf.writestr(info, data)


def make_docx(paragraphs: int, changes: int) -> bytes:
    """Build a deterministic ZIP_STORED DOCX with exactly ``changes`` bold defects."""
    if not (0 <= changes <= paragraphs):
        raise ValueError("changes must be between zero and paragraphs")
    body = []
    for index in range(paragraphs):
        bold = "<w:b/>" if index < changes else '<w:b w:val="0"/>'
        body.append(
            f'<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            f'<w:r><w:rPr>{bold}<w:sz w:val="24"/></w:rPr>'
            f'<w:t>Paragraph {index:04d} deterministic benchmark text.</w:t></w:r></w:p>'
        )
    document = (
        f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>'
        + "".join(body)
        + "</w:body></w:document>"
    ).encode("utf-8")
    styles = (
        f'<w:styles xmlns:w="{W}">'
        '<w:style w:type="paragraph" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/></w:style></w:styles>'
    ).encode("utf-8")
    content_types = (
        f'<?xml version="1.0"?><Types xmlns="{CT}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        f'<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    ).encode("utf-8")
    root_rels = (
        f'<Relationships xmlns="{PR}"><Relationship Id="rId1" '
        f'Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>'
    ).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        _part(zf, "[Content_Types].xml", content_types)
        _part(zf, "_rels/.rels", root_rels)
        _part(zf, "word/document.xml", document)
        _part(zf, "word/styles.xml", styles)
    return buffer.getvalue()


def profile_bytes() -> bytes:
    return (
        b'{"schema_version":"0.3","profile":{"id":"benchmark-0059",'
        b'"version":"1"},"rules":{"body":{"bold":{"mode":"exact",'
        b'"value":false}}}}'
    )


class Timings:
    def __init__(self, progress_path: Path | None = None) -> None:
        self.seconds: dict[str, float] = defaultdict(float)
        self.calls: dict[str, int] = defaultdict(int)
        self.applied_changes = 0
        self.progress_path = progress_path

    def progress(self, stage: str) -> None:
        if self.progress_path is None:
            return
        payload = {
            "last_stage": stage,
            "stage_calls": dict(self.calls),
            "applied_changes": self.applied_changes,
        }
        temporary = self.progress_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temporary.replace(self.progress_path)

    def wrap(self, label: str, function: Callable[..., Any]) -> Callable[..., Any]:
        def measured(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                self.seconds[label] += time.perf_counter() - started
                self.calls[label] += 1
                if label == "transform_record":
                    self.applied_changes += 1
                self.progress(label)

        measured.__name__ = getattr(function, "__name__", label)
        return measured


def install_instrumentation(timing: Timings) -> Callable[[], None]:
    """Patch only module-local imported names and return an undo function."""
    from formatador_academico import product_delivery
    from formatador_academico.processing_session import engine
    from formatador_academico.patcher import applicator

    targets = [
        (engine, "resolve_run_formatting", "formatting_resolution"),
        (engine, "resolve_paragraph_formatting", "formatting_resolution"),
        (engine, "build_style_catalog", "analysis"),
        (engine, "classify_document", "classification"),
        (engine, "_build_decisions", "decision"),
        (engine, "build_operation_plan", "planning"),
        (engine, "evaluate_operation_plan", "safety_gate"),
        (engine, "apply_cleared_operation", "patch_total"),
        (engine, "build_transform_record", "transform_record"),
        (applicator, "mutate_run", "xml_mutation"),
        (applicator, "mutate_paragraph", "xml_mutation"),
        (applicator, "serialize_document_xml", "xml_mutation"),
        (applicator, "repackage", "zip_repackaging"),
        (applicator, "validate_allowed_delta", "allowed_delta_validation"),
        (applicator, "verify_postcondition", "postcondition"),
        (product_delivery, "build_product_delivery", "final_delivery"),
    ]
    originals: list[tuple[Any, str, Any]] = []
    for module, name, label in targets:
        original = getattr(module, name)
        originals.append((module, name, original))
        setattr(module, name, timing.wrap(label, original))

    original_parser = engine.DocxParser

    class TimedDocxParser(original_parser):
        def parse_bytes(self, *args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            try:
                return super().parse_bytes(*args, **kwargs)
            finally:
                timing.seconds["parse"] += time.perf_counter() - started
                timing.calls["parse"] += 1
                timing.progress("parse")

    originals.append((engine, "DocxParser", original_parser))
    setattr(engine, "DocxParser", TimedDocxParser)

    def undo() -> None:
        for module, name, original in reversed(originals):
            setattr(module, name, original)

    return undo


def _hash_parts(package: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(package)) as zf:
        return {
            info.filename: hashlib.sha256(zf.read(info.filename)).hexdigest()
            for info in zf.infolist()
            if not info.is_dir()
        }


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        return value.value
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _ir_counts(package: bytes) -> tuple[int, int]:
    from formatador_academico.docx_parser import DocxParser

    ir = DocxParser().parse_bytes(package)
    paragraphs = 0
    runs = 0

    def visit(records: Any) -> None:
        nonlocal paragraphs, runs
        if not isinstance(records, list):
            return
        for record in records:
            if not isinstance(record, dict):
                continue
            source_type = record.get("source_type")
            if source_type == "paragraph":
                paragraphs += 1
            elif source_type == "run_raw":
                runs += 1
            visit(record.get("children"))

    for story in ir.get("stories", ()):
        if isinstance(story, dict):
            visit(story.get("blocks"))
    return paragraphs, runs


def _environment() -> dict[str, Any]:
    import importlib.metadata
    import zlib

    memory = None
    if sys.platform == "darwin":
        try:
            memory = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
        except (OSError, subprocess.CalledProcessError, ValueError):
            pass
    else:
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    memory = int(line.split()[1]) * 1024
                    break
        except (OSError, ValueError):
            pass
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    try:
        lxml_version = importlib.metadata.version("lxml")
    except importlib.metadata.PackageNotFoundError:
        lxml_version = None
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "cpu": platform.processor(),
        "ram_bytes": memory,
        "lxml": lxml_version,
        "zlib": zlib.ZLIB_VERSION,
        "commit": commit,
    }


def run_worker(paragraphs: int, changes: int, instrumented: bool,
               progress_path: Path | None = None) -> dict[str, Any]:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from formatador_academico import product_delivery
    from formatador_academico.product_input_boundary import build_product_from_inputs

    package = make_docx(paragraphs, changes)
    produced_paragraphs, produced_runs = _ir_counts(package)
    if produced_paragraphs != paragraphs or produced_runs != paragraphs:
        raise RuntimeError("fixture parser counts do not match the requested shape")
    timing = Timings(progress_path)
    undo = install_instrumentation(timing) if instrumented else lambda: None
    started = time.perf_counter()
    try:
        bundle = build_product_from_inputs(package, profile_bytes())
        delivery_started = time.perf_counter()
        delivery = product_delivery.build_product_delivery(bundle, base_name="benchmark-0059")
        delivery_elapsed = time.perf_counter() - delivery_started
    finally:
        undo()
    total = time.perf_counter() - started
    report = bundle.processing_report
    transforms = [
        {
            "target": _json_value(item.target.structural_path),
            "desired_value": _json_value(item.desired_applied),
        }
        for item in report.applied_changes
    ]
    # AppliedChangeItem is report-level data. The transform count is the
    # authoritative operation count for the benchmark's controlled fixture.
    output_parts = _hash_parts(bundle.clean_package_bytes)
    review_parts = _hash_parts(bundle.review_package_bytes)
    delivery_metadata = [
        {
            "role": item.role.value,
            "filename": item.filename,
            "media_type": item.media_type,
            "sha256": item.content_sha256,
            "size_bytes": item.size_bytes,
        }
        for item in delivery.files
    ]
    result = {
        "paragraphs": paragraphs,
        "expected_changes": changes,
        "input_bytes": len(package),
        "input_sha256": hashlib.sha256(package).hexdigest(),
        "output_parts_sha256": output_parts,
        "review_parts_sha256": review_parts,
        "report_sha256": hashlib.sha256(bundle.processing_report_json_bytes).hexdigest(),
        "applied_changes": report.summary.applied_change_count,
        "review_items": report.summary.review_item_count,
        "unapplied_changes": report.summary.unapplied_change_count,
        "session_status": report.summary.session_status.value,
        "transform_refs": transforms,
        "delivery_files": len(delivery.files),
        "delivery_metadata": delivery_metadata,
        "total_seconds": total,
        "final_delivery_seconds": delivery_elapsed,
        "stage_seconds": dict(timing.seconds),
        "stage_calls": dict(timing.calls),
        **_environment(),
        "peak_rss_bytes": _memory_peak(),
        "pid": os.getpid(),
    }
    timing.progress("complete")
    return result


def _memory_peak() -> int | None:
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value * 1024 if sys.platform != "darwin" else value)
    except (ImportError, AttributeError):
        return None


def run_case(script: Path, paragraphs: int, changes: int, timeout: float,
             instrumented: bool) -> dict[str, Any]:
    command = [sys.executable, str(script), "--worker", str(paragraphs), str(changes)]
    progress_file = Path(tempfile.mkstemp(prefix="benchmark-0059-progress-", suffix=".json")[1])
    command += ["--progress-file", str(progress_file)]
    if instrumented:
        command.append("--instrumented")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONPATH": str(SRC)},
        )
    except subprocess.TimeoutExpired:
        progress = {}
        if progress_file.exists():
            try:
                progress = json.loads(progress_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                progress = {}
        progress.update({"complete": False, "paragraphs": paragraphs,
                         "expected_changes": changes,
                         "elapsed_seconds": time.perf_counter() - started,
                         "timeout_seconds": timeout})
        progress_file.unlink(missing_ok=True)
        return progress
    if completed.returncode != 0:
        progress_file.unlink(missing_ok=True)
        raise RuntimeError(f"benchmark worker failed: {completed.stderr[-2000:]}")
    result = json.loads(completed.stdout)
    result["complete"] = True
    result["worker_wall_seconds"] = time.perf_counter() - started
    progress_file.unlink(missing_ok=True)
    return result


def cases() -> list[tuple[str, int, int]]:
    result = [(f"A{i}", size, 5) for i, size in enumerate((50, 100, 200, 400, 800), 1)]
    result += [(f"B{i}", 400, changes) for i, changes in enumerate((0, 1, 5, 10, 20, 40, 80, 160), 1)]
    result += [("C1", 100, 40), ("C2", 800, 20)]
    return result


def run_suite(args: argparse.Namespace) -> None:
    selected = set(args.only.split(",")) if args.only else None
    records = []
    for case_id, paragraphs, changes in cases():
        if selected and case_id not in selected:
            continue
        reference = run_case(Path(__file__), paragraphs, changes, args.timeout, False)
        if reference.get("complete"):
            if not (
                reference["applied_changes"] == changes
                and reference["session_status"] == "quiescent"
                and reference["review_items"] == 0
                and reference["unapplied_changes"] == 0
            ):
                raise RuntimeError(f"fixture did not produce exactly {changes} clean changes in {case_id}")
            measured = [run_case(Path(__file__), paragraphs, changes, args.timeout, True) for _ in range(args.repeats)]
            for item in measured:
                if item.get("complete") and (
                    {key: item.get(key) for key in _equivalence_keys()}
                    != {key: reference.get(key) for key in _equivalence_keys()}
                ):
                    raise RuntimeError(f"instrumented output differs from reference for {case_id}")
        else:
            measured = []
        records.append({
            "case": case_id,
            "reference": reference,
            "runs": measured,
            "statistics": _statistics(measured),
        })
    result = {
        "benchmark": "formatador-academico-cycle-0059",
        "tool": str(Path(__file__).relative_to(ROOT)),
        "repeats": args.repeats,
        "timeout_seconds": args.timeout,
        "cases": records,
    }
    output = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


def _equivalence_keys() -> tuple[str, ...]:
    return (
        "output_parts_sha256", "review_parts_sha256", "report_sha256",
        "applied_changes", "review_items", "unapplied_changes",
        "session_status", "transform_refs", "delivery_files", "delivery_metadata",
    )


def _statistics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs or not all(item.get("complete") for item in runs):
        return {}
    import statistics

    fields = ["total_seconds", "final_delivery_seconds", "peak_rss_bytes"]
    stage_names = sorted({stage for item in runs for stage in item.get("stage_seconds", {})})
    fields.extend(f"stage:{stage}" for stage in stage_names)
    result: dict[str, Any] = {}
    for field in fields:
        values = [
            (item.get("stage_seconds", {}).get(field[6:], 0.0) if field.startswith("stage:")
             else item.get(field))
            for item in runs
        ]
        result[field] = {
            "min": min(values),
            "median": statistics.median(values),
            "max": max(values),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2, metavar=("PARAGRAPHS", "CHANGES"), help=argparse.SUPPRESS)
    parser.add_argument("--instrumented", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--progress-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--only", help="comma-separated case ids, e.g. A1,B1,C1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        paragraphs, changes = map(int, args.worker)
        result = run_worker(paragraphs, changes, instrumented=args.instrumented,
                            progress_path=args.progress_file)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    if args.repeats < 1 or args.timeout <= 0:
        parser.error("--repeats must be positive and --timeout must be greater than zero")
    run_suite(args)


if __name__ == "__main__":
    main()
