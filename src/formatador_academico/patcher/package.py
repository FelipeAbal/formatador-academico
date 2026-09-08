"""Patcher v0.1 — in-memory OPC/ZIP package handling (decision 0028 §6/§23).

The patcher operates exclusively on the supplied snapshot bytes: no external
paths, no re-open, no clock. Repackaging preserves the frozen metadata
allowlist of every entry (filename, date_time, compress_type,
external_attr, internal_attr, create_system, per-entry comment, directory
identity) and the archive comment, and keeps the entry set and entry order
byte-for-byte. A fresh ZipInfo is built from the allowlist only — stale CRC,
compress_size, header_offset, ZIP64 extras and data-descriptor flag bits are
never copied. Compression level is fixed explicitly for determinism.
"""

from __future__ import annotations

import io
import zipfile

from .model import DOCUMENT_PART, PatcherContractError, PatcherIntegrityError

# Explicitly fixed compression level (zlib level 6): identical input bytes
# produce identical output bytes within the supported runtime contract.
FIXED_COMPRESS_LEVEL = 6

_METADATA_ALLOWLIST = (
    "filename",
    "date_time",
    "compress_type",
    "external_attr",
    "internal_attr",
    "create_system",
    "comment",
)


def read_package_parts(snapshot: bytes) -> tuple[list[zipfile.ZipInfo], dict[str, bytes], bytes]:
    """Open the snapshot ZIP purely in memory and read every entry.

    Returns (infolist in entry order, payloads by filename, archive comment).
    """

    if not isinstance(snapshot, bytes):
        raise PatcherContractError("package_snapshot must be bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(snapshot), "r") as zf:
            infos = zf.infolist()
            payloads = {info.filename: zf.read(info.filename) for info in infos}
            return infos, payloads, zf.comment
    except zipfile.BadZipFile as exc:
        raise PatcherContractError(f"package snapshot is not a valid ZIP: {exc}") from exc


def _fresh_zip_info(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    """New ZipInfo carrying ONLY the preserved-metadata allowlist."""

    fresh = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
    fresh.compress_type = info.compress_type
    fresh.external_attr = info.external_attr
    fresh.internal_attr = info.internal_attr
    fresh.create_system = info.create_system
    fresh.comment = info.comment
    return fresh


def repackage(
    infos: list[zipfile.ZipInfo],
    payloads: dict[str, bytes],
    archive_comment: bytes,
    new_document_xml: bytes,
) -> bytes:
    """Build the output package: only word/document.xml payload differs."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.comment = archive_comment
        for info in infos:
            fresh = _fresh_zip_info(info)
            if info.is_dir():
                zf.writestr(fresh, b"")
                continue
            data = new_document_xml if info.filename == DOCUMENT_PART else payloads[info.filename]
            if fresh.compress_type == zipfile.ZIP_DEFLATED:
                zf.writestr(fresh, data, compresslevel=FIXED_COMPRESS_LEVEL)
            else:
                zf.writestr(fresh, data)
    return buffer.getvalue()


def _metadata_of(info: zipfile.ZipInfo) -> tuple:
    return tuple(getattr(info, name) for name in _METADATA_ALLOWLIST) + (info.is_dir(),)


def verify_package_scope(original: bytes, output: bytes) -> None:
    """Fail-fast proof that the mutation stayed inside word/document.xml.

    Re-reads BOTH packages and requires: identical entry set, identical
    entry order, identical metadata allowlist per entry, identical archive
    comment, and byte-identical payload for every part except
    word/document.xml. Any divergence is a PatcherIntegrityError.
    """

    with zipfile.ZipFile(io.BytesIO(original), "r") as zf_in:
        in_infos = zf_in.infolist()
        in_comment = zf_in.comment
        in_payloads = {i.filename: zf_in.read(i.filename) for i in in_infos}
    with zipfile.ZipFile(io.BytesIO(output), "r") as zf_out:
        out_infos = zf_out.infolist()
        out_comment = zf_out.comment
        out_payloads = {i.filename: zf_out.read(i.filename) for i in out_infos}

    in_names = [i.filename for i in in_infos]
    out_names = [i.filename for i in out_infos]
    if in_names != out_names:
        raise PatcherIntegrityError(
            f"package entry set/order changed: {in_names!r} != {out_names!r}"
        )
    if in_comment != out_comment:
        raise PatcherIntegrityError("archive-level ZIP comment changed")
    for before, after in zip(in_infos, out_infos):
        if _metadata_of(before) != _metadata_of(after):
            raise PatcherIntegrityError(
                f"preserved ZIP metadata changed for entry {before.filename!r}"
            )
        if before.filename == DOCUMENT_PART:
            continue
        if in_payloads[before.filename] != out_payloads[before.filename]:
            raise PatcherIntegrityError(
                f"untouched part payload changed: {before.filename!r}"
            )
