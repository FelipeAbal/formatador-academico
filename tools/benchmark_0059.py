#!/usr/bin/env python3
"""Reproducible Cycle 0059 benchmark.

Modes
- Synthetic (default): deterministic DOCX fixtures across the size and
  change-count axes. Every case must produce exactly the expected clean
  changes with the product's default operation limit.
- Real documents (``--docx``): measures existing DOCX files in place, read
  only. There is no expected change count; each run records its outcome as
  the session status, ``timeout`` or ``error``.

The worker always uses ``build_product_from_inputs`` and, for the end-to-end
number, ``build_product_delivery``. No production module is edited by this
tool; instrumentation replaces names already imported by production modules,
only inside the worker process.

Variants and official numbers
- ``reference``: no stage timers. Its ``total_seconds`` is the OFFICIAL total.
- ``instrumented``: stage timers. Used for the stage breakdown only, never for
  the official total.
Both variants emit the same coarse progress boundaries, so progress I/O is
identical across variants and never happens inside a per-run call.

Run order
Within a case, runs follow the fixed ABBA schedule returned by ``schedule``:
reference, instrumented, instrumented, reference, ... This balances linear
drift between the variants. No randomness is used. Every run records its
global ``sequence``, ``case_position``, ``started_at`` and ``finished_at``.

Stage timings (also emitted as ``timing_semantics``)
- ``stage_seconds`` holds INCLUSIVE times.
- ``stage_seconds_exclusive`` holds parent buckets minus their measured
  children, following ``STAGE_HIERARCHY``.
- ``parse`` is the evaluation parse only. The postcondition parse is counted
  only as ``postcondition_parse``.
- ``total_seconds`` includes final bundle assembly (report and review DOCX),
  which has no stage timer, the coarse progress writes, and
  ``final_delivery``.
Stage buckets must not be summed as if they were exclusive.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import itertools
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TOOL = Path(__file__).resolve()
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
FIXED_DATE = (1980, 1, 1, 0, 0, 0)

# Test-only hook: park the worker after a progress boundary so that timeout
# behaviour can be tested deterministically. Never set it during measurement.
TEST_HOLD_ENV = "BENCHMARK_0059_TEST_HOLD_AFTER"
WORKER_ERROR_EXIT = 3

STAGE_HIERARCHY: dict[str, tuple[str, ...]] = {
    "decision": ("formatting_resolution",),
    "patch_total": (
        "xml_mutation",
        "zip_repackaging",
        "allowed_delta_validation",
        "postcondition",
    ),
    "postcondition": (
        "postcondition_parse",
        "postcondition_style_catalog",
        "postcondition_target_resolution",
        "postcondition_formatting_resolution",
    ),
}

TIMING_SEMANTICS: dict[str, Any] = {
    "official_total_variant": "reference",
    "official_total_field": "total_seconds",
    "stage_seconds": "inclusive per bucket; instrumented runs only",
    "stage_seconds_exclusive": "parent bucket minus its measured children",
    "hierarchy": {parent: list(children) for parent, children in STAGE_HIERARCHY.items()},
    "disjoint_top_level_stages": [
        "parse", "analysis", "classification", "decision",
        "planning", "safety_gate", "patch_total", "transform_record",
    ],
    "parse": "evaluation parse only; the postcondition parse is postcondition_parse",
    "total_seconds": (
        "build_product_from_inputs plus build_product_delivery, including untimed "
        "final bundle assembly and coarse progress writes"
    ),
    "schedule": "ABBA within each case: reference, instrumented, instrumented, reference, ...",
}

# Real academic profile used by --docx when --profile is not given.
ACADEMIC_PROFILE_BYTES = (
    b'{"schema_version":"0.3","profile":{"id":"benchmark-0059-academic",'
    b'"version":"1"},"rules":{"body":{"alignment":{"mode":"exact","value":"justify"},'
    b'"font_size":{"mode":"exact","value":12},'
    b'"line_spacing":{"mode":"exact","value":1.5}}}}'
)


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


def _test_hold(stage: str | None) -> None:
    target = os.environ.get(TEST_HOLD_ENV)
    if target and stage == target:
        time.sleep(3600)


class Progress:
    """Coarse progress boundaries, identical for reference and instrumented runs.

    Writes happen at evaluation start and end, after each transform record,
    around report and review DOCX assembly, around final delivery, when the
    input shape is known, and at completion. Nothing is written inside
    per-run or per-paragraph calls.
    """

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._started = time.perf_counter()
        self.current_stage: str | None = None
        self.last_completed_stage: str | None = None
        self.evaluations_started = 0
        self.patches_completed = 0
        self.applied_changes = 0
        self.writes = 0
        self.details: dict[str, Any] = {}

    def snapshot(self) -> dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "last_completed_stage": self.last_completed_stage,
            "evaluations_started": self.evaluations_started,
            "patches_completed": self.patches_completed,
            "applied_changes": self.applied_changes,
            "worker_elapsed_seconds": round(time.perf_counter() - self._started, 3),
            **self.details,
        }

    def _write(self) -> None:
        if self.path is not None:
            temporary = self.path.with_name(self.path.name + ".tmp")
            temporary.write_text(json.dumps(self.snapshot(), sort_keys=True), encoding="utf-8")
            temporary.replace(self.path)
            self.writes += 1
        _test_hold(self.last_completed_stage)

    def begin(self, stage: str) -> None:
        self.current_stage = stage
        if stage == "evaluation":
            self.evaluations_started += 1
        self._write()

    def end(self, stage: str) -> None:
        self.current_stage = None
        self.last_completed_stage = stage
        self._write()

    def note(self, **details: Any) -> None:
        self.details.update(details)
        self._write()


class Timings:
    def __init__(self) -> None:
        self.seconds: dict[str, float] = defaultdict(float)
        self.calls: dict[str, int] = defaultdict(int)

    def wrap(self, label: str, function: Callable[..., Any]) -> Callable[..., Any]:
        def measured(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                self.seconds[label] += time.perf_counter() - started
                self.calls[label] += 1

        measured.__name__ = getattr(function, "__name__", label)
        return measured


def _timed_parser(original: type, label: str, timing: Timings) -> type:
    class TimedDocxParser(original):  # type: ignore[misc, valid-type]
        def parse_bytes(self, *args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            try:
                return super().parse_bytes(*args, **kwargs)
            finally:
                timing.seconds[label] += time.perf_counter() - started
                timing.calls[label] += 1

    return TimedDocxParser


def install_instrumentation(timing: Timings) -> Callable[[], None]:
    """Patch only module-local imported names and return an undo function.

    ``patcher.validation`` names are used only by ``verify_postcondition``, so
    their timers belong to the postcondition and never to the evaluation.
    """
    from formatador_academico import product_delivery
    from formatador_academico.patcher import applicator, validation
    from formatador_academico.processing_session import engine

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
        (validation, "build_style_catalog", "postcondition_style_catalog"),
        (validation, "find_story", "postcondition_target_resolution"),
        (validation, "resolve_target", "postcondition_target_resolution"),
        (validation, "resolve_run_formatting", "postcondition_formatting_resolution"),
        (validation, "resolve_paragraph_formatting", "postcondition_formatting_resolution"),
        (product_delivery, "build_product_delivery", "final_delivery"),
    ]
    originals: list[tuple[Any, str, Any]] = []
    for module, name, label in targets:
        original = getattr(module, name)
        originals.append((module, name, original))
        setattr(module, name, timing.wrap(label, original))

    for module, label in ((engine, "parse"), (validation, "postcondition_parse")):
        original_parser = module.DocxParser
        originals.append((module, "DocxParser", original_parser))
        setattr(module, "DocxParser", _timed_parser(original_parser, label, timing))

    def undo() -> None:
        for module, name, original in reversed(originals):
            setattr(module, name, original)

    return undo


def install_progress(progress: Progress) -> Callable[[], None]:
    """Install coarse progress boundaries as the outermost layer, outside timers."""
    import formatador_academico.product_output_bundle.builder as bundle_builder
    from formatador_academico.processing_session import engine

    originals: list[tuple[Any, str, Any]] = []

    def replace(module: Any, name: str, factory: Callable[[Any], Any]) -> None:
        original = getattr(module, name)
        originals.append((module, name, original))
        setattr(module, name, factory(original))

    def around(stage: str) -> Callable[[Any], Any]:
        def factory(original: Any) -> Any:
            def boundary(*args: Any, **kwargs: Any) -> Any:
                progress.begin(stage)
                result = original(*args, **kwargs)
                progress.end(stage)
                return result

            return boundary

        return factory

    def count_patch(original: Any) -> Any:
        def boundary(*args: Any, **kwargs: Any) -> Any:
            result = original(*args, **kwargs)
            progress.patches_completed += 1
            return result

        return boundary

    def count_transform(original: Any) -> Any:
        def boundary(*args: Any, **kwargs: Any) -> Any:
            result = original(*args, **kwargs)
            progress.applied_changes += 1
            progress.end("transform_record")
            return result

        return boundary

    replace(engine, "_evaluate", around("evaluation"))
    replace(engine, "apply_cleared_operation", count_patch)
    replace(engine, "build_transform_record", count_transform)
    replace(bundle_builder, "build_processing_report", around("report_build"))
    replace(bundle_builder, "build_review_docx", around("review_docx_build"))

    def undo() -> None:
        for module, name, original in reversed(originals):
            setattr(module, name, original)

    return undo


def exclusive_seconds(inclusive: dict[str, float]) -> dict[str, float]:
    return {
        parent: inclusive[parent] - sum(inclusive.get(child, 0.0) for child in children)
        for parent, children in STAGE_HIERARCHY.items()
        if parent in inclusive
    }


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
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_value(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _ir_counts(package: bytes) -> tuple[int, int]:
    """Count paragraphs and raw runs in the main document story."""
    from formatador_academico.docx_parser import DocxParser
    from formatador_academico.safety_gate.targets import walk_records

    ir = DocxParser().parse_bytes(package)
    paragraphs = 0
    runs = 0
    for story in ir.get("stories") or ():
        if not isinstance(story, dict) or story.get("part") != "word/document.xml":
            continue
        for record, _ancestors in walk_records(story.get("blocks") or ()):
            source_type = record.get("source_type")
            if source_type == "paragraph":
                paragraphs += 1
            elif source_type == "run_raw":
                runs += 1
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


def _memory_peak() -> int | None:
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value * 1024 if sys.platform != "darwin" else value)
    except (ImportError, AttributeError):
        return None


def _ensure_src() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))


def _run_pipeline(package: bytes, profile: bytes, instrumented: bool,
                  progress: Progress) -> dict[str, Any]:
    from formatador_academico import product_delivery
    from formatador_academico.product_input_boundary import build_product_from_inputs

    timing = Timings()
    undo_timing = install_instrumentation(timing) if instrumented else (lambda: None)
    undo_progress = install_progress(progress)
    started = time.perf_counter()
    try:
        bundle = build_product_from_inputs(package, profile)
        progress.begin("final_delivery")
        delivery_started = time.perf_counter()
        delivery = product_delivery.build_product_delivery(bundle, base_name="benchmark-0059")
        delivery_elapsed = time.perf_counter() - delivery_started
        progress.end("final_delivery")
    finally:
        undo_progress()
        undo_timing()
    total = time.perf_counter() - started
    report = bundle.processing_report
    inclusive = dict(timing.seconds)
    share = None
    if inclusive.get("patch_total"):
        share = inclusive.get("postcondition", 0.0) / inclusive["patch_total"]
    return {
        "variant": "instrumented" if instrumented else "reference",
        "output_parts_sha256": _hash_parts(bundle.clean_package_bytes),
        "review_parts_sha256": _hash_parts(bundle.review_package_bytes),
        "report_sha256": hashlib.sha256(bundle.processing_report_json_bytes).hexdigest(),
        "applied_changes": report.summary.applied_change_count,
        "review_items": report.summary.review_item_count,
        "unapplied_changes": report.summary.unapplied_change_count,
        "session_status": report.summary.session_status.value,
        "transform_refs": [
            {
                "target": _json_value(item.target.structural_path),
                "property_slot": _json_value(item.target.property_slot),
                "desired_value": _json_value(item.desired_applied),
            }
            for item in report.applied_changes
        ],
        "delivery_files": len(delivery.files),
        "delivery_metadata": [
            {
                "role": item.role.value,
                "filename": item.filename,
                "media_type": item.media_type,
                "sha256": item.content_sha256,
                "size_bytes": item.size_bytes,
            }
            for item in delivery.files
        ],
        "total_seconds": total,
        "final_delivery_seconds": delivery_elapsed,
        "stage_seconds": inclusive,
        "stage_seconds_exclusive": exclusive_seconds(inclusive),
        "stage_calls": dict(timing.calls),
        "postcondition_share_of_patch_total": share,
        **_environment(),
        "peak_rss_bytes": _memory_peak(),
        "pid": os.getpid(),
    }


def run_worker(paragraphs: int, changes: int, instrumented: bool,
               progress_path: Path | None = None) -> dict[str, Any]:
    _ensure_src()
    package = make_docx(paragraphs, changes)
    progress = Progress(progress_path)
    produced_paragraphs, produced_runs = _ir_counts(package)
    if produced_paragraphs != paragraphs or produced_runs != paragraphs:
        raise RuntimeError("fixture parser counts do not match the requested shape")
    progress.note(paragraphs=produced_paragraphs, runs=produced_runs)
    result = _run_pipeline(package, profile_bytes(), instrumented, progress)
    result.update({
        "mode": "synthetic",
        "paragraphs": paragraphs,
        "runs": produced_runs,
        "expected_changes": changes,
        "input_bytes": len(package),
        "input_sha256": hashlib.sha256(package).hexdigest(),
    })
    progress.end("complete")
    result["progress_writes"] = progress.writes
    return result


def run_docx_worker(docx_path: Path, profile_path: Path | None, instrumented: bool,
                    progress_path: Path | None = None) -> dict[str, Any]:
    """Measure a real DOCX read in place. The file is never written or copied."""
    _ensure_src()
    docx_path = Path(docx_path)
    package = docx_path.read_bytes()
    input_sha = hashlib.sha256(package).hexdigest()
    profile = Path(profile_path).read_bytes() if profile_path else ACADEMIC_PROFILE_BYTES
    progress = Progress(progress_path)
    paragraphs, runs = _ir_counts(package)
    progress.note(paragraphs=paragraphs, runs=runs)
    result = _run_pipeline(package, profile, instrumented, progress)
    result.update({
        "mode": "docx",
        "label": docx_path.name,
        "paragraphs": paragraphs,
        "runs": runs,
        "input_bytes": len(package),
        "input_sha256": input_sha,
        "input_unchanged_in_memory": hashlib.sha256(package).hexdigest() == input_sha,
        "input_unchanged_on_disk": hashlib.sha256(docx_path.read_bytes()).hexdigest() == input_sha,
        "profile_source": "file" if profile_path else "builtin-academic-0059",
        "profile_sha256": hashlib.sha256(profile).hexdigest(),
    })
    progress.end("complete")
    result["progress_writes"] = progress.writes
    return result


def _read_progress(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _spawn(worker_args: list[str], timeout: float, strict: bool,
           script: Path = TOOL) -> dict[str, Any]:
    descriptor, name = tempfile.mkstemp(prefix="benchmark-0059-progress-", suffix=".json")
    os.close(descriptor)
    progress_file = Path(name)
    command = [sys.executable, str(script), *worker_args, "--progress-file", str(progress_file)]
    record: dict[str, Any] = {"started_at": _now()}
    started = time.perf_counter()
    try:
        try:
            completed = subprocess.run(
                command, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout,
                env={**os.environ, "PYTHONPATH": str(SRC)},
            )
        except subprocess.TimeoutExpired:
            record.update(_read_progress(progress_file))
            record.update({"complete": False, "outcome": "timeout", "timeout_seconds": timeout})
            return record
        if completed.returncode != 0:
            if strict:
                raise RuntimeError(f"benchmark worker failed: {completed.stderr[-2000:]}")
            record.update(_read_progress(progress_file))
            if completed.returncode == WORKER_ERROR_EXIT:
                try:
                    record.update(json.loads(completed.stdout))
                except json.JSONDecodeError:
                    record["error_type"] = "unreadable_worker_error"
            else:
                record["error_type"] = f"worker_exit_{completed.returncode}"
            record.update({"complete": False, "outcome": "error"})
            return record
        record.update(json.loads(completed.stdout))
        record.update({"complete": True, "outcome": record.get("session_status")})
        return record
    finally:
        record["finished_at"] = _now()
        record["worker_wall_seconds"] = time.perf_counter() - started
        progress_file.unlink(missing_ok=True)
        progress_file.with_name(progress_file.name + ".tmp").unlink(missing_ok=True)


def run_case(script: Path, paragraphs: int, changes: int, timeout: float,
             instrumented: bool) -> dict[str, Any]:
    worker_args = ["--worker", str(paragraphs), str(changes)]
    if instrumented:
        worker_args.append("--instrumented")
    record = _spawn(worker_args, timeout, strict=True, script=script)
    record.setdefault("paragraphs", paragraphs)
    record.setdefault("expected_changes", changes)
    return record


def run_docx_case(docx_path: Path, profile_path: Path | None, timeout: float,
                  instrumented: bool) -> dict[str, Any]:
    worker_args = ["--worker-docx", str(docx_path)]
    if profile_path is not None:
        worker_args += ["--worker-profile", str(profile_path)]
    if instrumented:
        worker_args.append("--instrumented")
    record = _spawn(worker_args, timeout, strict=False)
    record.setdefault("label", Path(docx_path).name)
    return record


def cases() -> list[tuple[str, int, int]]:
    result = [(f"A{i}", size, 5) for i, size in enumerate((50, 100, 200, 400, 800), 1)]
    result += [(f"B{i}", 400, changes) for i, changes in enumerate((0, 1, 5, 10, 20, 40, 80, 160), 1)]
    result += [("C1", 100, 40), ("C2", 800, 20)]
    return result


def schedule(repeats: int) -> list[str]:
    """Fixed ABBA order: reference, instrumented, instrumented, reference, ..."""
    order: list[str] = []
    for index in range(repeats):
        if index % 2 == 0:
            order.extend(("reference", "instrumented"))
        else:
            order.extend(("instrumented", "reference"))
    return order


def _equivalence_keys() -> tuple[str, ...]:
    return (
        "output_parts_sha256", "review_parts_sha256", "report_sha256",
        "applied_changes", "review_items", "unapplied_changes",
        "session_status", "transform_refs", "delivery_files", "delivery_metadata",
    )


def _equivalence(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in _equivalence_keys()}


def _execute_case(label: str, spawn: Callable[[bool], dict[str, Any]], repeats: int,
                  validate: Callable[[dict[str, Any]], None] | None,
                  sequence: Iterator[int], strict_equivalence: bool) -> dict[str, Any]:
    """Run one case on the ABBA schedule.

    After a timeout or error, the other variant still runs once if it has not
    run yet, as a diagnostic; the case then stops.
    """
    planned = schedule(repeats)
    runs: list[dict[str, Any]] = []
    baseline: dict[str, Any] | None = None
    mismatches: list[int] = []
    variants_run: set[str] = set()
    interrupted = False
    for position, variant in enumerate(planned, 1):
        if interrupted and variant in variants_run:
            break
        record = spawn(variant == "instrumented")
        record.update({"variant": variant, "case_position": position, "sequence": next(sequence)})
        runs.append(record)
        variants_run.add(variant)
        if record.get("complete"):
            if baseline is None:
                if validate is not None:
                    validate(record)
                baseline = record
            elif _equivalence(record) != _equivalence(baseline):
                if strict_equivalence:
                    raise RuntimeError(
                        f"output of run {position} ({variant}) differs from the first complete run in {label}"
                    )
                mismatches.append(position)
        elif record.get("outcome") in ("timeout", "error"):
            interrupted = True
    result: dict[str, Any] = {
        "planned_runs": len(planned),
        "skipped_runs": len(planned) - len(runs),
        "stopped_early": len(runs) < len(planned),
        "runs": runs,
        "statistics": _statistics(runs),
    }
    if not strict_equivalence:
        result["equivalence_mismatch_positions"] = mismatches
    return result


def _summary(values: list[Any]) -> dict[str, Any] | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return {
        "min": min(present),
        "median": statistics.median(present),
        "max": max(present),
        "n": len(present),
    }


def _statistics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"official_total_variant": "reference"}
    for variant in ("reference", "instrumented"):
        chosen = [run for run in runs if run.get("variant") == variant]
        complete = [run for run in chosen if run.get("complete")]
        block: dict[str, Any] = {
            "complete_runs": len(complete),
            "incomplete_runs": len(chosen) - len(complete),
        }
        for field in ("total_seconds", "final_delivery_seconds", "peak_rss_bytes"):
            summary = _summary([run.get(field) for run in complete])
            if summary is not None:
                block[field] = summary
        if variant == "instrumented":
            stages = sorted({stage for run in complete for stage in run.get("stage_seconds", {})})
            block["stage_seconds"] = {
                stage: _summary([run["stage_seconds"].get(stage, 0.0) for run in complete])
                for stage in stages
            }
            parents = sorted({stage for run in complete for stage in run.get("stage_seconds_exclusive", {})})
            block["stage_seconds_exclusive"] = {
                stage: _summary([run["stage_seconds_exclusive"].get(stage, 0.0) for run in complete])
                for stage in parents
            }
            share = _summary([run.get("postcondition_share_of_patch_total") for run in complete])
            if share is not None:
                block["postcondition_share_of_patch_total"] = share
        result[variant] = block
    reference_total = result["reference"].get("total_seconds")
    instrumented_total = result["instrumented"].get("total_seconds")
    if reference_total and instrumented_total:
        result["instrumentation_overhead_median_seconds"] = (
            instrumented_total["median"] - reference_total["median"]
        )
    return result


def _envelope(mode: str, args: argparse.Namespace, started_at: str) -> dict[str, Any]:
    return {
        "benchmark": "formatador-academico-cycle-0059",
        "tool": str(TOOL.relative_to(ROOT)),
        "mode": mode,
        "repeats": args.repeats,
        "timeout_seconds": args.timeout,
        "schedule": TIMING_SEMANTICS["schedule"],
        "timing_semantics": TIMING_SEMANTICS,
        "started_at": started_at,
        "finished_at": _now(),
    }


def _emit(result: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def run_suite(args: argparse.Namespace,
              case_list: list[tuple[str, int, int]] | None = None) -> dict[str, Any]:
    selected = set(args.only.split(",")) if args.only else None
    sequence = itertools.count(1)
    started_at = _now()
    records = []
    for case_id, paragraphs, changes in (case_list if case_list is not None else cases()):
        if selected and case_id not in selected:
            continue

        def spawn(instrumented: bool, paragraphs: int = paragraphs, changes: int = changes) -> dict[str, Any]:
            return run_case(TOOL, paragraphs, changes, args.timeout, instrumented)

        def validate(record: dict[str, Any], case_id: str = case_id, changes: int = changes) -> None:
            if not (
                record["applied_changes"] == changes
                and record["session_status"] == "quiescent"
                and record["review_items"] == 0
                and record["unapplied_changes"] == 0
            ):
                raise RuntimeError(f"fixture did not produce exactly {changes} clean changes in {case_id}")

        outcome = _execute_case(case_id, spawn, args.repeats, validate, sequence, strict_equivalence=True)
        records.append({"case": case_id, "paragraphs": paragraphs, "expected_changes": changes, **outcome})
    result = _envelope("synthetic", args, started_at)
    result["cases"] = records
    _emit(result, args.output)
    return result


def run_docx_suite(args: argparse.Namespace) -> dict[str, Any]:
    sequence = itertools.count(1)
    started_at = _now()
    profile = args.profile.read_bytes() if args.profile else ACADEMIC_PROFILE_BYTES
    documents = []
    for docx_path in args.docx:
        docx_path = Path(docx_path)
        data = docx_path.read_bytes()
        metadata: dict[str, Any] = {
            "label": docx_path.name,
            "input_bytes": len(data),
            "input_sha256": hashlib.sha256(data).hexdigest(),
        }
        del data
        if args.record_docx_path:
            metadata["path"] = str(docx_path.resolve())

        def spawn(instrumented: bool, docx_path: Path = docx_path) -> dict[str, Any]:
            return run_docx_case(docx_path, args.profile, args.timeout, instrumented)

        outcome = _execute_case(docx_path.name, spawn, args.repeats, None, sequence, strict_equivalence=False)
        documents.append({**metadata, **outcome})
    result = _envelope("docx", args, started_at)
    result.update({
        "profile_source": "file" if args.profile else "builtin-academic-0059",
        "profile_sha256": hashlib.sha256(profile).hexdigest(),
        "privacy": (
            "DOCX files are read in place and never copied. Only label, size and "
            "SHA-256 are recorded; the absolute path only with --record-docx-path. "
            "Worker errors record the exception type and code, never the message."
        ),
        "documents": documents,
    })
    _emit(result, args.output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--worker", nargs=2, metavar=("PARAGRAPHS", "CHANGES"), help=argparse.SUPPRESS)
    parser.add_argument("--worker-docx", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-profile", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--instrumented", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--progress-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--only", help="comma-separated synthetic case ids, e.g. A1,B1,C1")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--docx", type=Path, action="append",
                        help="measure a real DOCX in place; repeat for several files")
    parser.add_argument("--profile", type=Path,
                        help="Profile Input JSON for --docx; default is the built-in academic profile")
    parser.add_argument("--record-docx-path", action="store_true",
                        help="also record the absolute path of each --docx file")
    args = parser.parse_args()

    if args.worker:
        paragraphs, changes = map(int, args.worker)
        result = run_worker(paragraphs, changes, instrumented=args.instrumented,
                            progress_path=args.progress_file)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    if args.worker_docx:
        try:
            result = run_docx_worker(args.worker_docx, args.worker_profile, args.instrumented,
                                     args.progress_file)
        except Exception as exc:  # recorded as outcome=error; the message may contain document text
            code = getattr(exc, "code", None)
            if not isinstance(code, (str, int, type(None))):
                code = str(code)
            print(json.dumps({"error_type": type(exc).__name__, "error_code": code}, sort_keys=True))
            raise SystemExit(WORKER_ERROR_EXIT)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return

    if args.repeats < 1 or args.timeout <= 0:
        parser.error("--repeats must be positive and --timeout must be greater than zero")
    if args.docx:
        if args.only:
            parser.error("--only applies to synthetic cases and cannot be combined with --docx")
        for docx_path in args.docx:
            if not docx_path.is_file():
                parser.error(f"--docx is not a file: {docx_path.name}")
        if args.profile is not None and not args.profile.is_file():
            parser.error("--profile is not a file")
        run_docx_suite(args)
        return
    if args.profile is not None or args.record_docx_path:
        parser.error("--profile and --record-docx-path require --docx")
    run_suite(args)


if __name__ == "__main__":
    main()
