#!/usr/bin/env python3
"""Exact-equivalence oracle fixed to the pre-0060 reference commit."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import fields
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


REFERENCE_COMMIT = "4bcda308a4975f2bb84d87ab4738faaed463bb75"
EXPECTED_SESSION_FIELDS = (
    "processing_session_version",
    "status",
    "profile_ref",
    "input_package_sha256",
    "output_package_sha256",
    "output_package_bytes",
    "transforms",
    "final_classifications",
    "final_decisions",
    "findings",
)
EXPECTED_FINDING_FIELDS = (
    "kind",
    "decision_ref",
    "operation_ref",
    "target",
    "reason",
)
EXPECTED_PROFILE_REF_FIELDS = ("profile_id", "profile_version")

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from artifact_comparator_0060 import (  # noqa: E402
    ArtifactDigest,
    compare_artifacts,
    comparison_json_bytes,
    digest_delivery,
)


class OracleError(RuntimeError):
    """Base class for oracle failures."""


class ReferenceMaterializationError(OracleError):
    """The fixed reference commit could not be materialized exactly."""


class WorkerError(OracleError):
    """An isolated reference or candidate worker failed."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_from_bytes(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"))


def _assert_exact_fields(instance: object, expected: tuple[str, ...], model_name: str) -> None:
    actual = tuple(field.name for field in fields(instance))
    if actual != expected:
        raise OracleError(
            f"{model_name} fields changed; expected {expected!r}, got {actual!r}"
        )


def _target_json(target: object) -> Mapping[str, Any]:
    from enum import Enum
    from decimal import Decimal

    def convert(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, tuple):
            return [convert(item) for item in value]
        if isinstance(value, list):
            return [convert(item) for item in value]
        if isinstance(value, dict):
            return {str(key): convert(item) for key, item in sorted(value.items())}
        if hasattr(value, "__dataclass_fields__"):
            return {
                field.name: convert(getattr(value, field.name))
                for field in fields(value)
            }
        return value

    converted = convert(target)
    if not isinstance(converted, dict):
        raise TypeError("finding target must serialize to an object")
    return converted


def serialize_session_finding(finding: object) -> bytes:
    _assert_exact_fields(finding, EXPECTED_FINDING_FIELDS, "SessionFinding")
    payload = {
        "kind": finding.kind.value,
        "decision_ref": finding.decision_ref,
        "operation_ref": finding.operation_ref,
        "target": _target_json(finding.target),
        "reason": finding.reason,
    }
    return _canonical_json_bytes(payload)


def serialize_processing_session_result(result: object) -> bytes:
    """Canonical envelope required by decision 0060A section 3.3."""

    from formatador_academico.classification.serialization import (
        serialize_classification_result,
    )
    from formatador_academico.decision.serialization import serialize_decision
    from formatador_academico.transform_log.serialization import (
        serialize_transform_record,
    )

    _assert_exact_fields(result, EXPECTED_SESSION_FIELDS, "ProcessingSessionResult")
    _assert_exact_fields(result.profile_ref, EXPECTED_PROFILE_REF_FIELDS, "ProfileRef")
    payload = {
        "processing_session_version": result.processing_session_version,
        "status": result.status.value,
        "profile_ref": {
            "profile_id": result.profile_ref.profile_id,
            "profile_version": result.profile_ref.profile_version,
        },
        "input_package_sha256": result.input_package_sha256,
        "output_package_sha256": result.output_package_sha256,
        "output_package_bytes_sha256": _sha(result.output_package_bytes),
        "transforms": [
            _json_from_bytes(serialize_transform_record(item))
            for item in result.transforms
        ],
        "final_classifications": [
            _json_from_bytes(serialize_classification_result(item))
            for item in result.final_classifications
        ],
        "final_decisions": [
            _json_from_bytes(serialize_decision(item))
            for item in result.final_decisions
        ],
        "findings": [
            _json_from_bytes(serialize_session_finding(item))
            for item in result.findings
        ],
    }
    return _canonical_json_bytes(payload)


def _activate_source_root(source_root: Path) -> None:
    source_root = source_root.resolve()
    package_dir = source_root / "src" / "formatador_academico"
    if not package_dir.is_dir():
        raise WorkerError(f"source root does not contain src/formatador_academico: {source_root}")
    sys.path.insert(0, str(source_root / "src"))


def build_observation(
    package_snapshot: bytes,
    profile_json_bytes: bytes,
    *,
    base_name: str,
    max_applied_operations: int,
) -> dict[str, Any]:
    """Run the frozen public pipeline and emit hashes only."""

    from formatador_academico.classification.serialization import (
        serialize_classification_result,
    )
    from formatador_academico.decision.serialization import serialize_decision
    from formatador_academico.docx_parser import DocxParser, serialize_parse_result
    from formatador_academico.processing_session import process_document
    from formatador_academico.product_delivery import build_product_delivery
    from formatador_academico.product_input_boundary import build_product_from_inputs
    from formatador_academico.profile_input import processing_profile_from_json
    from formatador_academico.transform_log.serialization import (
        serialize_transform_record,
        transform_ref,
    )

    parse_result = DocxParser().parse_bytes(package_snapshot)
    profile = processing_profile_from_json(profile_json_bytes)
    session = process_document(
        package_snapshot,
        profile,
        max_applied_operations=max_applied_operations,
    )
    bundle = build_product_from_inputs(
        package_snapshot,
        profile_json_bytes,
        max_applied_operations=max_applied_operations,
    )
    delivery = build_product_delivery(bundle, base_name=base_name)
    if session.output_package_sha256 != bundle.clean_package_sha256:
        raise OracleError("session and delivery runs produced different clean package hashes")

    envelope = serialize_processing_session_result(session)
    artifacts = digest_delivery(delivery)
    return {
        "outcome": "success",
        "parse_result_sha256": _sha(serialize_parse_result(parse_result)),
        "processing_session_envelope_sha256": _sha(envelope),
        "session": {
            "status": session.status.value,
            "input_package_sha256": session.input_package_sha256,
            "output_package_sha256": session.output_package_sha256,
            "transform_refs": [transform_ref(item) for item in session.transforms],
            "transform_sha256": [
                _sha(serialize_transform_record(item)) for item in session.transforms
            ],
            "classification_sha256": [
                _sha(serialize_classification_result(item))
                for item in session.final_classifications
            ],
            "decision_sha256": [
                _sha(serialize_decision(item)) for item in session.final_decisions
            ],
            "finding_sha256": [
                _sha(serialize_session_finding(item)) for item in session.findings
            ],
        },
        "artifacts": [
            {
                "role": item.role,
                "filename": item.filename,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
            }
            for item in artifacts
        ],
    }


def build_observation_or_error(
    package_snapshot: bytes,
    profile_json_bytes: bytes,
    *,
    base_name: str,
    max_applied_operations: int,
) -> dict[str, Any]:
    """Observe failure paths without exposing exception text or input data."""

    try:
        return build_observation(
            package_snapshot,
            profile_json_bytes,
            base_name=base_name,
            max_applied_operations=max_applied_operations,
        )
    except Exception as exc:
        exception_type = f"{type(exc).__module__}.{type(exc).__qualname__}"
        return {
            "outcome": "error",
            "exception_type": exception_type,
            "exception_message_sha256": _sha(str(exc).encode("utf-8")),
        }


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


@contextlib.contextmanager
def materialized_reference(
    repo_root: Path,
    reference_commit: str = REFERENCE_COMMIT,
) -> Iterator[Path]:
    """Materialize and verify the exact reference commit in a temporary worktree."""

    available = _git(repo_root, "cat-file", "-e", f"{reference_commit}^{{commit}}")
    if available.returncode != 0:
        raise ReferenceMaterializationError(
            f"reference commit {reference_commit} is unavailable; refusing current-tree fallback"
        )

    with tempfile.TemporaryDirectory(prefix="oracle-0060-") as temp_dir:
        worktree = Path(temp_dir) / "reference"
        added = _git(repo_root, "worktree", "add", "--detach", "--quiet", str(worktree), reference_commit)
        if added.returncode != 0:
            raise ReferenceMaterializationError(
                f"could not materialize reference commit {reference_commit}: {added.stderr.strip()}"
            )
        try:
            actual = _git(worktree, "rev-parse", "HEAD")
            if actual.returncode != 0 or actual.stdout.strip() != reference_commit:
                raise ReferenceMaterializationError(
                    f"materialized reference does not match {reference_commit}"
                )
            yield worktree
        finally:
            removed = _git(repo_root, "worktree", "remove", "--force", str(worktree))
            if removed.returncode != 0 and worktree.exists():
                raise ReferenceMaterializationError(
                    f"could not remove temporary reference worktree: {removed.stderr.strip()}"
                )


def run_worker(
    source_root: Path,
    package_path: Path,
    profile_path: Path,
    *,
    base_name: str,
    max_applied_operations: int,
    hash_seed: str | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    src = str(source_root.resolve() / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    if hash_seed is not None:
        env["PYTHONHASHSEED"] = hash_seed
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_worker",
        "--source-root",
        str(source_root),
        "--package",
        str(package_path),
        "--profile",
        str(profile_path),
        "--base-name",
        base_name,
        "--max-applied-operations",
        str(max_applied_operations),
    ]
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
        raise WorkerError(f"isolated oracle worker failed: {detail}")
    try:
        return json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerError("isolated oracle worker returned invalid JSON") from exc


def _artifact_records(observation: Mapping[str, Any]) -> tuple[ArtifactDigest, ...]:
    return tuple(ArtifactDigest(**item) for item in observation["artifacts"])


def compare_against_reference(
    repo_root: Path,
    package_path: Path,
    profile_path: Path,
    *,
    base_name: str = "oracle-0060",
    max_applied_operations: int = 10000,
) -> dict[str, Any]:
    with materialized_reference(repo_root) as reference_root:
        reference = run_worker(
            reference_root,
            package_path,
            profile_path,
            base_name=base_name,
            max_applied_operations=max_applied_operations,
        )
    candidate = run_worker(
        repo_root,
        package_path,
        profile_path,
        base_name=base_name,
        max_applied_operations=max_applied_operations,
    )
    if reference.get("outcome") == "success" and candidate.get("outcome") == "success":
        artifact_comparison = compare_artifacts(
            _artifact_records(reference),
            _artifact_records(candidate),
            reference_commit=REFERENCE_COMMIT,
        )
        artifact_payload: dict[str, Any] | None = _json_from_bytes(
            comparison_json_bytes(artifact_comparison)
        )
        artifacts_equal = artifact_comparison.equal
    else:
        artifact_payload = None
        artifacts_equal = "artifacts" not in reference and "artifacts" not in candidate
    non_artifact_reference = {k: v for k, v in reference.items() if k != "artifacts"}
    non_artifact_candidate = {k: v for k, v in candidate.items() if k != "artifacts"}
    non_artifact_equal = non_artifact_reference == non_artifact_candidate
    return {
        "equal": non_artifact_equal and artifacts_equal,
        "reference_commit": REFERENCE_COMMIT,
        "reference": non_artifact_reference,
        "candidate": non_artifact_candidate,
        "artifact_comparison": artifact_payload,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare = subparsers.add_parser("compare")
    compare.add_argument("--repo-root", type=Path, default=Path.cwd())
    compare.add_argument("--package", type=Path, required=True)
    compare.add_argument("--profile", type=Path, required=True)
    compare.add_argument("--base-name", default="oracle-0060")
    compare.add_argument("--max-applied-operations", type=int, default=10000)

    worker = subparsers.add_parser("_worker")
    worker.add_argument("--source-root", type=Path, required=True)
    worker.add_argument("--package", type=Path, required=True)
    worker.add_argument("--profile", type=Path, required=True)
    worker.add_argument("--base-name", required=True)
    worker.add_argument("--max-applied-operations", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "_worker":
            _activate_source_root(args.source_root)
            observation = build_observation_or_error(
                args.package.read_bytes(),
                args.profile.read_bytes(),
                base_name=args.base_name,
                max_applied_operations=args.max_applied_operations,
            )
            print(_canonical_json_bytes(observation).decode("utf-8"))
            return 0

        comparison = compare_against_reference(
            args.repo_root.resolve(),
            args.package.resolve(),
            args.profile.resolve(),
            base_name=args.base_name,
            max_applied_operations=args.max_applied_operations,
        )
        print(_canonical_json_bytes(comparison).decode("utf-8"))
        return 0 if comparison["equal"] else 1
    except OracleError as exc:
        print(f"oracle_0060: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
