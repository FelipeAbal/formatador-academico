"""Patcher v0.1 — document-level XML parse/serialize (decision 0028 §7).

Serialization ALWAYS operates on the ElementTree (document level), never on
the root alone, so comments/PIs before/after the document element and the
XML declaration semantics (including standalone) survive the patch. The
original XML declaration bytes are preserved verbatim.

Parser settings mirror the frozen parser: resolve_entities=False,
no_network=True, recover=False, DTD/DOCTYPE rejected.
"""

from __future__ import annotations

import io
import re

from lxml import etree

from .model import PatcherIntegrityError

_DECLARATION_RE = re.compile(rb"^(\s*<\?xml.*?\?>)(\s*)", re.DOTALL)


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

    if b"<!DOCTYPE" in data.upper():
        raise PatcherIntegrityError(f"DTD/DOCTYPE is not allowed in OOXML part: {part_name}")
    try:
        return etree.parse(io.BytesIO(data), parser=_xml_parser())
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise PatcherIntegrityError(f"malformed XML in {part_name}: {exc}") from exc


def serialize_document_xml(tree: etree._ElementTree, original_bytes: bytes) -> bytes:
    """Serialize the full document tree, preserving the original declaration.

    The XML declaration (version/encoding/standalone) is replayed verbatim
    from the original part bytes, including its original lexical form; the
    remaining document (root + prolog/epilog comments and PIs) comes from
    ElementTree-level serialization. No cleanup_namespaces, ever.
    """

    payload = etree.tostring(tree, encoding="utf-8", xml_declaration=False)
    match = _DECLARATION_RE.match(original_bytes)
    if match is None:
        return payload
    declaration, spacing = match.group(1), match.group(2)
    return declaration + spacing + payload
