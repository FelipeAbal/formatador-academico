#!/usr/bin/env python3
"""Privacy-preserving artifact comparator for cycle 0060.

The comparator keeps only the delivery role, filename, byte length and
SHA-256.  It never emits artifact contents or input paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROLE_ORDER = (
    "clean_docx",
    "review_docx",
    "technical_report",
    "human_report",
    "manifest",
)


@dataclass(frozen=True)
class ArtifactDigest:
    role: str
    filename: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if self.role not in ROLE_ORDER:
            raise ValueError(f"unknown delivery role: {self.role!r}")
        if (
            not self.filename
            or "/" in self.filename
            or "\\" in self.filename
            or Path(self.filename).name != self.filename
        ):
            raise ValueError("filename must be a non-empty basename")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError("sha256 must be a lowercase hexadecimal digest")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")


@dataclass(frozen=True)
class ArtifactMismatch:
    role: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class ArtifactComparison:
    equal: bool
    reference_commit: str
    reference: tuple[ArtifactDigest, ...]
    candidate: tuple[ArtifactDigest, ...]
    mismatches: tuple[ArtifactMismatch, ...]


def digest_bytes(role: str, filename: str, content: bytes) -> ArtifactDigest:
    if type(content) is not bytes:
        raise TypeError("content must be exact bytes")
    return ArtifactDigest(
        role=role,
        filename=filename,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )


def digest_delivery(delivery: object) -> tuple[ArtifactDigest, ...]:
    """Digest a ProductDelivery without retaining or returning its bytes."""

    files = getattr(delivery, "files", None)
    if not isinstance(files, tuple):
        raise TypeError("delivery.files must be a tuple")
    records = tuple(
        digest_bytes(item.role.value, item.filename, item.content_bytes)
        for item in files
    )
    _validate_role_order(records)
    return records


def _validate_role_order(records: Sequence[ArtifactDigest]) -> None:
    roles = tuple(record.role for record in records)
    if roles != ROLE_ORDER:
        raise ValueError(f"artifact roles must follow ROLE_ORDER; got {roles!r}")


def compare_artifacts(
    reference: Sequence[ArtifactDigest],
    candidate: Sequence[ArtifactDigest],
    *,
    reference_commit: str,
) -> ArtifactComparison:
    if (
        len(reference_commit) != 40
        or any(c not in "0123456789abcdef" for c in reference_commit)
    ):
        raise ValueError("reference_commit must be a full lowercase Git SHA")
    reference_tuple = tuple(reference)
    candidate_tuple = tuple(candidate)
    _validate_role_order(reference_tuple)
    _validate_role_order(candidate_tuple)

    mismatches: list[ArtifactMismatch] = []
    for expected, actual in zip(reference_tuple, candidate_tuple):
        fields = tuple(
            name
            for name in ("filename", "sha256", "size_bytes")
            if getattr(expected, name) != getattr(actual, name)
        )
        if fields:
            mismatches.append(ArtifactMismatch(expected.role, fields))

    result = ArtifactComparison(
        equal=not mismatches,
        reference_commit=reference_commit,
        reference=reference_tuple,
        candidate=candidate_tuple,
        mismatches=tuple(mismatches),
    )
    return result


def comparison_json_bytes(comparison: ArtifactComparison) -> bytes:
    payload = asdict(comparison)
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def records_json_bytes(records: Iterable[ArtifactDigest]) -> bytes:
    return json.dumps(
        [asdict(record) for record in records],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _load_records(path: Path) -> tuple[ArtifactDigest, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("artifact manifest must be a JSON array")
    records = tuple(ArtifactDigest(**item) for item in raw)
    _validate_role_order(records)
    return records


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="reference digest manifest")
    parser.add_argument("candidate", type=Path, help="candidate digest manifest")
    parser.add_argument("--reference-commit", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    comparison = compare_artifacts(
        _load_records(args.reference),
        _load_records(args.candidate),
        reference_commit=args.reference_commit,
    )
    print(comparison_json_bytes(comparison).decode("utf-8"))
    return 0 if comparison.equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
