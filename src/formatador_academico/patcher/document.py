"""Patcher v0.1 — document-level XML parse/serialize (decision 0028 §7).

Serialization ALWAYS operates on the ElementTree (document level), never on
the root alone, so comments/PIs before/after the document element and XML
declaration semantics (version/encoding/standalone) survive the patch.

Parser settings mirror the frozen parser: resolve_entities=False,
no_network=True, recover=False, DTD/DOCTYPE rejected.
"""

from __future__ import annotations

import io
import re

from lxml import etree

from .model import PatcherIntegrityError

_DECL_RE = re.compile(r"^(\ufeff?\s*<\?xml.*?\?>)(\s*)", re.DOTALL)


def _xml_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        remove_blank_text=False,
        strip_cdata=False,
        recover=False,
        huge_tree=False,
    )


def parse_document_xml(data: bytes, part_name: str) -> etree._ElementTree:
    """Parse one OOXML part at document level (ElementTree, docinfo kept)."""

    # UTF-16/32 encode ASCII with NUL bytes, so the byte substring check is
    # intentionally only a fast-path. libxml2 still has entity resolution
    # disabled; parser-level DTD content is never usable by the patcher.
    if b"<!DOCTYPE" in data.upper():
        raise PatcherIntegrityError(f"DTD/DOCTYPE is not allowed in OOXML part: {part_name}")
    try:
        tree = etree.parse(io.BytesIO(data), parser=_xml_parser())
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise PatcherIntegrityError(f"malformed XML in {part_name}: {exc}") from exc
    if tree.docinfo.doctype:
        raise PatcherIntegrityError(f"DTD/DOCTYPE is not allowed in OOXML part: {part_name}")
    return tree


def _physical_encoding(original_bytes: bytes, docinfo_encoding: str | None) -> str:
    """Choose serialization encoding from physical BOM/signature first.

    libxml2 may report UTF-8 for a UTF-16 byte stream without an XML
    declaration, so docinfo alone is not a sufficient source of truth.
    """

    data = original_bytes
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return "UTF-32"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "UTF-16"
    if data.startswith(b"\xef\xbb\xbf"):
        return "UTF-8-SIG"
    if data.startswith((b"<\x00?\x00x\x00m\x00l\x00", b"<\x00w\x00:", b"<\x00w\x00d\x00")):
        return "UTF-16LE"
    if data.startswith((b"\x00<\x00?\x00x\x00m\x00l", b"\x00<\x00w\x00:")):
        return "UTF-16BE"
    return docinfo_encoding or "UTF-8"


def _codec_name(encoding: str) -> str:
    """Python codec name for decoding/re-encoding declaration text."""

    upper = encoding.upper().replace("_", "-")
    if upper == "UTF-8-SIG":
        return "utf-8-sig"
    if upper in ("UTF-16", "UTF-16LE", "UTF-16BE", "UTF-32"):
        return upper.lower()
    return encoding


def _strip_serialization_bom(payload: bytes, encoding: str) -> bytes:
    upper = encoding.upper().replace("_", "-")
    if upper == "UTF-16" and payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        return payload[2:]
    if upper == "UTF-32" and payload.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return payload[4:]
    if upper == "UTF-8-SIG" and payload.startswith(b"\xef\xbb\xbf"):
        return payload[3:]
    return payload


def _original_declaration(original_bytes: bytes, encoding: str) -> tuple[str, str] | None:
    """Return exact declaration text + following whitespace, if present."""

    try:
        text = original_bytes.decode(_codec_name(encoding))
    except (LookupError, UnicodeDecodeError):
        return None
    match = _DECL_RE.match(text)
    if match is None:
        return None
    declaration = match.group(1).lstrip("\ufeff")
    return declaration, match.group(2)


def serialize_document_xml(tree: etree._ElementTree, original_bytes: bytes) -> bytes:
    """Serialize the full tree in the original physical XML encoding.

    If the input had an XML declaration, its lexical text is preserved while
    the body is serialized in the same physical encoding. If the input had no
    declaration, none is introduced. This avoids both UTF-8/UTF-16 mismatches
    and lxml's behavior of emitting a declaration when ``standalone`` is
    supplied with ``xml_declaration=False``.
    """

    docinfo = tree.docinfo
    encoding = _physical_encoding(original_bytes, docinfo.encoding)
    declaration = _original_declaration(original_bytes, encoding)

    if declaration is None:
        try:
            return etree.tostring(tree, encoding=encoding, xml_declaration=False)
        except (LookupError, ValueError, TypeError) as exc:
            raise PatcherIntegrityError(
                f"unable to serialize word/document.xml in original encoding {encoding!r}: {exc}"
            ) from exc

    declaration_text, spacing = declaration
    # Serialize only the document body/prolog/epilog; replay the original
    # declaration lexically so quote style/casing/standalone are preserved.
    body_encoding = "UTF-8" if encoding.upper().replace("_", "-") == "UTF-8-SIG" else encoding
    try:
        payload = etree.tostring(tree, encoding=body_encoding, xml_declaration=False)
    except (LookupError, ValueError, TypeError) as exc:
        raise PatcherIntegrityError(
            f"unable to serialize word/document.xml in original encoding {encoding!r}: {exc}"
        ) from exc
    payload = _strip_serialization_bom(payload, encoding)

    codec = _codec_name(encoding)
    try:
        prefix = (declaration_text + spacing).encode(codec)
    except (LookupError, UnicodeEncodeError) as exc:
        raise PatcherIntegrityError(
            f"unable to preserve XML declaration in original encoding {encoding!r}: {exc}"
        ) from exc
    return prefix + payload
