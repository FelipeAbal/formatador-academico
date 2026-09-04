from __future__ import annotations

from typing import Any

from lxml import etree

from .model import (
    AnalysisWarning,
    NormalizedParagraph,
    NormalizedSegment,
    SegmentKind,
    SourceAnchor,
    TextRole,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_MAPPING: dict[str, tuple[SegmentKind, TextRole, bool, str | None]] = {
    "text": (SegmentKind.TEXT, TextRole.CONTENT, True, "__raw__"),
    "tab": (SegmentKind.TAB, TextRole.CONTENT, True, "\t"),
    "break": (SegmentKind.LINE_BREAK, TextRole.CONTENT, True, "__break__"),
    "carriage_return": (SegmentKind.CARRIAGE_RETURN, TextRole.CONTENT, True, "\r"),
    "no_break_hyphen": (SegmentKind.NO_BREAK_HYPHEN, TextRole.CONTENT, True, "\u2011"),
    "soft_hyphen": (SegmentKind.SOFT_HYPHEN, TextRole.CONTENT, True, "\u00ad"),
    "symbol": (SegmentKind.SYMBOL, TextRole.OPAQUE, False, None),
    "instruction_text": (SegmentKind.FIELD_CODE, TextRole.FIELD_INTERNAL, False, None),
    "deleted_text": (SegmentKind.DELETED_TEXT, TextRole.DELETED, False, None),
}


_OPAQUE_SOURCE_TYPES = {
    "opaque_fragment",
    "non_element_fragment",
    "opaque_container_child",
    "opaque_paragraph_child",
    "non_element_paragraph_child",
}


def _break_type(canonical_xml: str) -> str | None:
    """Return the raw w:type of a break, "" when absent, None when unreadable."""
    try:
        node = etree.fromstring(canonical_xml.encode("utf-8"), parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=False))
    except (etree.XMLSyntaxError, ValueError):
        return None
    return node.get(f"{{{W_NS}}}type") or ""


def _anchor(fragment: dict[str, Any], story_id: str, part: str, fragment_type: str, raw_text: str | None) -> SourceAnchor:
    return SourceAnchor(
        story_id=story_id,
        part=part,
        structural_path=fragment["structural_path"],
        physical_hash=fragment["physical_hash"],
        fragment_type=fragment_type,
        source_start=0,
        source_end=len(raw_text) if raw_text is not None else 0,
    )


def _segment(fragment: dict[str, Any], story_id: str, part: str, cursor: int, warnings: list[AnalysisWarning]) -> NormalizedSegment:
    fragment_type = fragment.get("fragment_type")
    if fragment_type not in _MAPPING:
        warnings.append(AnalysisWarning(
            code="normalized_unexpected_fragment",
            message=f"Fragment type {fragment_type!r} not recognized by v0.1a mapping.",
            structural_path=fragment["structural_path"],
        ))
        raw_text = fragment.get("text")
        return NormalizedSegment(
            SegmentKind.OPAQUE, TextRole.OPAQUE, raw_text, None, cursor, cursor, False,
            _anchor(fragment, story_id, part, fragment_type or fragment.get("source_type", "unknown"), raw_text), None,
        )

    kind, role, contributes, projection = _MAPPING[fragment_type]
    raw_text: str | None = None
    metadata: tuple[tuple[str, str | None], ...] | None = None

    if fragment_type in {"text", "instruction_text", "deleted_text"}:
        raw_text = fragment.get("text", "")
    if projection == "__raw__":
        projected_text = raw_text
    elif projection == "__break__":
        btype = _break_type(fragment.get("canonical_xml", ""))
        if btype in {"", "textWrapping"}:
            kind, role, contributes, projected_text = SegmentKind.LINE_BREAK, TextRole.CONTENT, True, "\n"
        elif btype == "page":
            kind, role, contributes, projected_text = SegmentKind.PAGE_BREAK, TextRole.STRUCTURAL, False, None
        elif btype == "column":
            kind, role, contributes, projected_text = SegmentKind.COLUMN_BREAK, TextRole.STRUCTURAL, False, None
        else:
            # Conservative policy: unknown/unreadable break type never becomes
            # a silent LINE_BREAK (no false precision). Zero-width opaque + warning.
            detail = "unreadable canonical_xml" if btype is None else f"unknown w:type {btype!r}"
            warnings.append(AnalysisWarning(
                code="normalized_unknown_break_type",
                message=f"Break fragment not projected: {detail}.",
                structural_path=fragment["structural_path"],
            ))
            kind, role, contributes, projected_text = SegmentKind.OPAQUE, TextRole.OPAQUE, False, None
    else:
        projected_text = projection

    if fragment_type == "symbol":
        sym = fragment.get("symbol") or {}
        metadata = (("font", sym.get("font")), ("char", sym.get("char")))

    logical_end = cursor + len(projected_text) if contributes and projected_text is not None else cursor
    return NormalizedSegment(
        segment_kind=kind,
        text_role=role,
        raw_text=raw_text,
        projected_text=projected_text,
        logical_start=cursor,
        logical_end=logical_end,
        contributes_to_default_text=contributes,
        source=_anchor(fragment, story_id, part, fragment_type, raw_text),
        metadata=metadata,
    )


def _walk(node: dict[str, Any], story_id: str, part: str, segments: list[NormalizedSegment], warnings: list[AnalysisWarning], cursor: int) -> int:
    source_type = node.get("source_type")
    if source_type in {"run_raw", "run_container"}:
        for child in node.get("children", []):
            cursor = _walk(child, story_id, part, segments, warnings, cursor)
        return cursor
    if source_type == "text_fragment":
        seg = _segment(node, story_id, part, cursor, warnings)
        segments.append(seg)
        return seg.logical_end
    if source_type in _OPAQUE_SOURCE_TYPES:
        seg = NormalizedSegment(
            SegmentKind.OPAQUE, TextRole.OPAQUE, None, None, cursor, cursor, False,
            _anchor(node, story_id, part, node.get("fragment_type") or source_type, None), None,
        )
        segments.append(seg)
        return cursor
    # Unknown node in the paragraph tree: never drop silently.
    if node.get("structural_path") and node.get("physical_hash"):
        warnings.append(AnalysisWarning(
            code="normalized_unexpected_fragment",
            message=f"PhysicalIR node with source_type {source_type!r} not recognized by v0.1a traversal.",
            structural_path=node["structural_path"],
        ))
        seg = NormalizedSegment(
            SegmentKind.OPAQUE, TextRole.OPAQUE, None, None, cursor, cursor, False,
            _anchor(node, story_id, part, source_type or "unknown", None), None,
        )
        segments.append(seg)
    return cursor


def normalize_paragraph(paragraph: dict[str, Any], story_id: str, part: str) -> NormalizedParagraph:
    if paragraph.get("source_type") != "paragraph":
        raise ValueError("normalize_paragraph requires a PhysicalIR paragraph record")
    if not paragraph.get("structural_path") or not paragraph.get("physical_hash"):
        raise ValueError("paragraph lacks provenance required by Analysis View")

    segments: list[NormalizedSegment] = []
    warnings: list[AnalysisWarning] = []
    cursor = 0
    for child in paragraph.get("children", []):
        cursor = _walk(child, story_id, part, segments, warnings, cursor)

    default_text = "".join(
        s.projected_text for s in segments
        if s.contributes_to_default_text and s.projected_text is not None
    )
    return NormalizedParagraph(
        paragraph_path=paragraph["structural_path"],
        paragraph_hash=paragraph["physical_hash"],
        segments=tuple(segments),
        default_text=default_text,
        has_non_content=any(not s.contributes_to_default_text for s in segments),
        analysis_warnings=tuple(warnings),
    )
