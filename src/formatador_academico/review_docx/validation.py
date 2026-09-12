"""Review DOCX v0.1 set-driven allowed-delta proof (decision 0036)."""
from __future__ import annotations

from lxml import etree

from .. import parser_api
from ..docx_parser import W_NS
from ..patcher.document import parse_document_xml
from ..patcher.validation import _c14n, _docinfo_fingerprint, _prolog_epilog
from .model import DOCUMENT_PART, ReviewDocxIntegrityError

W_R = f"{{{W_NS}}}r"
W_RPR = f"{{{W_NS}}}rPr"
W_HIGHLIGHT = f"{{{W_NS}}}highlight"
W_VAL = f"{{{W_NS}}}val"


def _direct(node: etree._Element, tag: str) -> list[etree._Element]:
    return [c for c in node if isinstance(c.tag, str) and c.tag == tag]


def _remove_after_highlight_only(
    before_run: etree._Element,
    after_run: etree._Element,
) -> None:
    """Neutralize only the review-created highlight on the AFTER side.

    If the before run had no direct rPr, the empty wrapper created solely by
    this layer is also removed from the after tree. Existing before-side
    highlights are never stripped, which makes accidental overwrite visible.
    """

    before_rprs = _direct(before_run, W_RPR)
    after_rprs = _direct(after_run, W_RPR)
    if len(after_rprs) != 1:
        raise ReviewDocxIntegrityError("marked output run must have exactly one direct w:rPr")
    after_rpr = after_rprs[0]
    highlights = _direct(after_rpr, W_HIGHLIGHT)
    if len(highlights) != 1 or dict(highlights[0].attrib) != {W_VAL: "yellow"}:
        raise ReviewDocxIntegrityError("marked output must contain canonical direct yellow highlight")
    after_rpr.remove(highlights[0])

    if not before_rprs:
        element_children = [c for c in after_rpr if isinstance(c.tag, str)]
        if not element_children and not after_rpr.attrib:
            after_run.remove(after_rpr)


def validate_allowed_delta(
    before_xml: bytes,
    after_xml: bytes,
    marked_paths: tuple[str, ...],
) -> None:
    """Prove that only direct yellow highlights were added at marked paths."""

    before_tree = parse_document_xml(before_xml, DOCUMENT_PART)
    after_tree = parse_document_xml(after_xml, DOCUMENT_PART)
    before_root = before_tree.getroot()
    after_root = after_tree.getroot()

    for path in marked_paths:
        try:
            before_run = parser_api.resolve_structural_path(before_root, path)
            after_run = parser_api.resolve_structural_path(after_root, path)
        except parser_api.StructuralPathError as exc:
            raise ReviewDocxIntegrityError(f"allowed-delta target resolution failed: {exc}") from exc
        if before_run.tag != W_R or after_run.tag != W_R:
            raise ReviewDocxIntegrityError("allowed-delta target is not w:r in both trees")
        _remove_after_highlight_only(before_run, after_run)

    if _c14n(before_root) != _c14n(after_root):
        raise ReviewDocxIntegrityError(
            "allowed-delta violation: document XML differs beyond review highlights"
        )
    if _prolog_epilog(before_root) != _prolog_epilog(after_root):
        raise ReviewDocxIntegrityError("allowed-delta violation: prolog/epilog changed")
    if _docinfo_fingerprint(before_tree) != _docinfo_fingerprint(after_tree):
        raise ReviewDocxIntegrityError("allowed-delta violation: XML declaration semantics changed")
