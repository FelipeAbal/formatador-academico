"""Patcher v0.1 — allowed-delta validator and semantic postcondition.

Contract: docs/decisions/0028-patcher-v01-contract.md §19-§22.

The validator is NOT a generic XML diff. It is a narrow proof that the only
semantic OOXML delta between the original and the produced
`word/document.xml` is the authorized target property (plus the rPr wrapper
when it had to be created), and it runs on bytes RE-READ from the produced
ZIP, never on the in-memory tree.

The postcondition re-opens the produced package bytes with the real frozen
Parser, rebuilds the StyleCatalog and re-derives the public Analysis for the
target run, requiring the resolved semantic value to equal the operation's
desired value. Every failure here is a fail-fast PatcherIntegrityError.
"""

from __future__ import annotations

import io
import zipfile

from lxml import etree

from ..analysis.formatting import resolve_paragraph_formatting, resolve_run_formatting
from ..analysis.formatting_model import Length, ResolutionStatus
from ..decision.model import LineSpacingValue
from ..analysis.style_catalog import build_style_catalog
from ..decision.model import DecisionKey
from ..decision.vocabulary import extract_resolved_value
from ..docx_parser import DocxParser, W_NS
from ..operation_plan.model import LengthValue
from ..safety_gate.targets import find_story, paragraph_ancestor, resolve_target
from .. import parser_api
from .document import parse_document_xml
from .model import DOCUMENT_PART, PatcherIntegrityError
from .xml_patch import PPR_CANONICAL_RANK, RPR_CANONICAL_RANK, W_B, W_JC, W_LINE, W_LINE_RULE, W_P, W_PPR, W_R, W_RPR, W_SPACING, W_SZ, W_VAL

_TARGET_TAG = {"bold": W_B, "font_size": W_SZ}
_TARGET_KEY = {
    "bold": DecisionKey("run", "P1", "bold"),
    "font_size": DecisionKey("run", "P2", "font_size"),
}


def _direct(node: etree._Element, tag: str) -> list[etree._Element]:
    return [c for c in node if isinstance(c.tag, str) and c.tag == tag]


def _c14n(root: etree._Element) -> bytes:
    """Inclusive c14n with comments — the parser's frozen canonical form."""

    return etree.tostring(root, method="c14n", exclusive=False, with_comments=True)


def _prolog_epilog(root: etree._Element) -> list[bytes]:
    """Serialized document-level siblings outside the root, in order."""

    nodes = []
    sibling = root.getprevious()
    while sibling is not None:
        nodes.append(sibling)
        sibling = sibling.getprevious()
    nodes.reverse()
    trailing = []
    sibling = root.getnext()
    while sibling is not None:
        trailing.append(sibling)
        sibling = sibling.getnext()
    return [etree.tostring(n) for n in nodes + trailing]


def _docinfo_fingerprint(tree: etree._ElementTree) -> tuple[str | None, str | None, bool | None]:
    """Declaration semantics relevant to safe round-trip validation."""

    info = tree.docinfo
    encoding = info.encoding.upper() if isinstance(info.encoding, str) else info.encoding
    return (info.xml_version, encoding, info.standalone)


def _strip_target_for_comparison(run: etree._Element, target_tag: str) -> None:
    """Remove the direct target property (and the emptied rPr wrapper)."""

    for rpr in _direct(run, W_RPR):
        for element in _direct(rpr, target_tag):
            rpr.remove(element)
        element_children = [c for c in rpr if isinstance(c.tag, str)]
        if not element_children and not rpr.attrib:
            run.remove(rpr)


def _check_output_property(run: etree._Element, property_slot: str, desired) -> None:
    """The final target property: canonical form AND canonical position."""

    rprs = _direct(run, W_RPR)
    if len(rprs) != 1:
        raise PatcherIntegrityError("output run must contain exactly one direct w:rPr")
    rpr = rprs[0]
    children = [c for c in rpr if isinstance(c.tag, str)]
    ranks = [RPR_CANONICAL_RANK.get(c.tag) for c in children]
    if any(rank is None for rank in ranks) or ranks != sorted(ranks):
        raise PatcherIntegrityError("output w:rPr children are not in canonical schema order")

    target_tag = _TARGET_TAG[property_slot]
    targets = _direct(rpr, target_tag)
    if len(targets) != 1:
        raise PatcherIntegrityError("output run must contain exactly one direct target property")
    element = targets[0]
    if [c for c in element if isinstance(c.tag, str)]:
        raise PatcherIntegrityError("output target property must not have element children")
    if property_slot == "bold":
        expected_attrib = {} if desired else {W_VAL: "0"}
        if dict(element.attrib) != expected_attrib:
            raise PatcherIntegrityError(
                f"output w:b is not the canonical representation: {dict(element.attrib)!r}"
            )
    else:
        if set(element.attrib) != {W_VAL}:
            raise PatcherIntegrityError("output w:sz must carry exactly w:val")
        lexical = element.get(W_VAL)
        if lexical != str(int(desired.value * 2)) or lexical.startswith("0"):
            raise PatcherIntegrityError(
                f"output w:sz lexical is not the canonical half-point integer: {lexical!r}"
            )


def _strip_alignment_for_comparison(paragraph: etree._Element) -> None:
    for ppr in _direct(paragraph, W_PPR):
        for element in _direct(ppr, W_JC):
            ppr.remove(element)
        if not [c for c in ppr if isinstance(c.tag, str)] and not ppr.attrib:
            paragraph.remove(ppr)


def _check_output_alignment(paragraph: etree._Element, desired: str) -> None:
    pprs = _direct(paragraph, W_PPR)
    if len(pprs) != 1:
        raise PatcherIntegrityError("output paragraph must contain exactly one direct w:pPr")
    ppr = pprs[0]
    ranks = [PPR_CANONICAL_RANK.get(c.tag) for c in ppr if isinstance(c.tag, str)]
    if any(rank is None for rank in ranks) or ranks != sorted(ranks):
        raise PatcherIntegrityError("output w:pPr children are not in canonical schema order")
    targets = _direct(ppr, W_JC)
    if len(targets) != 1:
        raise PatcherIntegrityError("output paragraph must contain exactly one direct w:jc")
    element = targets[0]
    if [c for c in element if isinstance(c.tag, str)] or set(element.attrib) != {W_VAL}:
        raise PatcherIntegrityError("output w:jc is not in the canonical shape")
    if element.get(W_VAL) != desired:
        raise PatcherIntegrityError(
            f"output w:jc lexical value {element.get(W_VAL)!r} != desired {desired!r}"
        )




def _line_twips(desired: LineSpacingValue) -> str:
    value = desired.value
    sign, digits, exponent = value.as_tuple()
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    if exponent >= 0:
        return str(coefficient * (10 ** exponent) * 240)
    numerator, denominator = coefficient * 240, 10 ** (-exponent)
    if numerator % denominator:
        raise PatcherIntegrityError("desired spacing.line is not exactly representable")
    return str(numerator // denominator)


def _strip_spacing_line_for_comparison(paragraph: etree._Element) -> None:
    for ppr in _direct(paragraph, W_PPR):
        for spacing in _direct(ppr, W_SPACING):
            for attr in (W_LINE, W_LINE_RULE):
                spacing.attrib.pop(attr, None)
            if not spacing.attrib and not [c for c in spacing if isinstance(c.tag, str)]:
                ppr.remove(spacing)
        if not [c for c in ppr if isinstance(c.tag, str)] and not ppr.attrib:
            paragraph.remove(ppr)


def _check_output_spacing_line(paragraph: etree._Element, desired: LineSpacingValue) -> None:
    pprs = _direct(paragraph, W_PPR)
    if len(pprs) != 1:
        raise PatcherIntegrityError("output paragraph must contain exactly one direct w:pPr")
    ppr = pprs[0]
    ranks = [PPR_CANONICAL_RANK.get(c.tag) for c in ppr if isinstance(c.tag, str)]
    if any(rank is None for rank in ranks) or ranks != sorted(ranks):
        raise PatcherIntegrityError("output w:pPr children are not in canonical schema order")
    targets = _direct(ppr, W_SPACING)
    if len(targets) != 1:
        raise PatcherIntegrityError("output paragraph must contain exactly one direct w:spacing")
    element = targets[0]
    if [c for c in element if isinstance(c.tag, str)]:
        raise PatcherIntegrityError("output w:spacing must not have element children")
    if element.get(W_LINE_RULE) != "auto" or element.get(W_LINE) != _line_twips(desired):
        raise PatcherIntegrityError("output w:spacing line is not canonical")


def _validate_alignment_delta(
    original_document_xml: bytes,
    output_document_xml: bytes,
    target_path: str,
    desired: str,
) -> None:
    original_tree = parse_document_xml(original_document_xml, DOCUMENT_PART)
    output_tree = parse_document_xml(output_document_xml, DOCUMENT_PART)
    try:
        original_paragraph = parser_api.resolve_structural_path(
            original_tree.getroot(), target_path
        )
        output_paragraph = parser_api.resolve_structural_path(
            output_tree.getroot(), target_path
        )
    except parser_api.StructuralPathError as exc:
        raise PatcherIntegrityError(f"alignment target resolution failed: {exc}") from exc
    if original_paragraph.tag != W_P or output_paragraph.tag != W_P:
        raise PatcherIntegrityError("alignment target is not a w:p in both documents")
    _check_output_alignment(output_paragraph, desired)
    _strip_alignment_for_comparison(original_paragraph)
    _strip_alignment_for_comparison(output_paragraph)
    if _c14n(original_tree.getroot()) != _c14n(output_tree.getroot()):
        raise PatcherIntegrityError(
            "allowed-delta violation: document XML differs beyond paragraph alignment"
        )
    if _prolog_epilog(original_tree.getroot()) != _prolog_epilog(output_tree.getroot()):
        raise PatcherIntegrityError(
            "allowed-delta violation: prolog/epilog comments/PIs changed"
        )
    if _docinfo_fingerprint(original_tree) != _docinfo_fingerprint(output_tree):
        raise PatcherIntegrityError(
            "allowed-delta violation: XML declaration semantics changed"
        )




def _validate_spacing_line_delta(original_document_xml: bytes, output_document_xml: bytes, target_path: str, desired: LineSpacingValue) -> None:
    original_tree = parse_document_xml(original_document_xml, DOCUMENT_PART)
    output_tree = parse_document_xml(output_document_xml, DOCUMENT_PART)
    try:
        original_paragraph = parser_api.resolve_structural_path(original_tree.getroot(), target_path)
        output_paragraph = parser_api.resolve_structural_path(output_tree.getroot(), target_path)
    except parser_api.StructuralPathError as exc:
        raise PatcherIntegrityError(f"spacing.line target resolution failed: {exc}") from exc
    if original_paragraph.tag != W_P or output_paragraph.tag != W_P:
        raise PatcherIntegrityError("spacing.line target is not a w:p in both documents")
    _check_output_spacing_line(output_paragraph, desired)
    _strip_spacing_line_for_comparison(original_paragraph)
    _strip_spacing_line_for_comparison(output_paragraph)
    if _c14n(original_tree.getroot()) != _c14n(output_tree.getroot()):
        raise PatcherIntegrityError("allowed-delta violation: document XML differs beyond paragraph spacing.line")
    if _prolog_epilog(original_tree.getroot()) != _prolog_epilog(output_tree.getroot()):
        raise PatcherIntegrityError("allowed-delta violation: XML prolog/epilog changed")
    if _docinfo_fingerprint(original_tree) != _docinfo_fingerprint(output_tree):
        raise PatcherIntegrityError("allowed-delta violation: XML declaration semantics changed")


def validate_allowed_delta(
    original_document_xml: bytes,
    output_document_xml: bytes,
    target_path: str,
    property_slot: str,
    desired,
) -> None:
    """Narrow authorized-delta proof over relread output bytes (§20)."""

    if property_slot == "spacing.line":
        _validate_spacing_line_delta(original_document_xml, output_document_xml, target_path, desired)
        return

    if property_slot == "alignment":
        _validate_alignment_delta(
            original_document_xml, output_document_xml, target_path, desired
        )
        return

    target_tag = _TARGET_TAG[property_slot]
    original_tree = parse_document_xml(original_document_xml, DOCUMENT_PART)
    output_tree = parse_document_xml(output_document_xml, DOCUMENT_PART)

    try:
        original_run = parser_api.resolve_structural_path(original_tree.getroot(), target_path)
        output_run = parser_api.resolve_structural_path(output_tree.getroot(), target_path)
    except parser_api.StructuralPathError as exc:
        raise PatcherIntegrityError(f"allowed-delta target resolution failed: {exc}") from exc
    if original_run.tag != W_R or output_run.tag != W_R:
        raise PatcherIntegrityError("allowed-delta target is not a w:r in both documents")

    # The output property itself is verified separately (canonical form and
    # canonical schema position) BEFORE the comparison trees are stripped.
    _check_output_property(output_run, property_slot, desired)

    _strip_target_for_comparison(original_run, target_tag)
    _strip_target_for_comparison(output_run, target_tag)

    if _c14n(original_tree.getroot()) != _c14n(output_tree.getroot()):
        raise PatcherIntegrityError(
            "allowed-delta violation: document XML differs beyond the authorized property"
        )
    if _prolog_epilog(original_tree.getroot()) != _prolog_epilog(output_tree.getroot()):
        raise PatcherIntegrityError(
            "allowed-delta violation: prolog/epilog comments/PIs changed"
        )
    if _docinfo_fingerprint(original_tree) != _docinfo_fingerprint(output_tree):
        raise PatcherIntegrityError(
            "allowed-delta violation: XML declaration semantics changed"
        )


def verify_postcondition(output_package_bytes: bytes, operation) -> None:
    """Re-parse the produced package and require semantic desired == current."""

    ir = DocxParser().parse_bytes(output_package_bytes)
    if ir["status"] != "ok":
        raise PatcherIntegrityError(
            f"output package did not re-parse cleanly: {ir.get('errors')!r}"
        )
    catalog = build_style_catalog(output_package_bytes, ir)
    if catalog.part_status not in ("ok", "missing"):
        raise PatcherIntegrityError(
            f"output StyleCatalog is not usable: {catalog.part_status!r}"
        )
    story = find_story(ir, DOCUMENT_PART)
    matches = resolve_target(story, operation.target.structural_path)
    if len(matches) != 1:
        raise PatcherIntegrityError(
            "postcondition target resolution did not yield exactly one record"
        )
    record, ancestors = matches[0]
    if operation.target.target_type == "paragraph":
        if record.get("source_type") != "paragraph":
            raise PatcherIntegrityError("postcondition target is not a paragraph record")
        analysis = resolve_paragraph_formatting(record, catalog, DOCUMENT_PART)
        key = DecisionKey("paragraph", operation.key.aspect_id, operation.key.property_slot)
        resolved = extract_resolved_value(key, analysis)
        if resolved.status is not ResolutionStatus.RESOLVED:
            raise PatcherIntegrityError(
                f"postcondition Analysis did not resolve paragraph alignment: {resolved.status}"
            )
        if operation.key.property_slot == "spacing.line":
            desired = operation.desired_value
            current = resolved.value
            if not isinstance(desired, LineSpacingValue):
                raise PatcherIntegrityError("spacing.line postcondition desired value is invalid")
            if current.rule != "auto" or current.unit != "multiple" or current.value != desired.value:
                raise PatcherIntegrityError(
                    f"postcondition mismatch: current {current!r} != desired {desired!r}"
                )
        elif resolved.value != operation.desired_value:
            raise PatcherIntegrityError(
                f"postcondition mismatch: current {resolved.value!r} != desired "
                f"{operation.desired_value!r}"
            )
        return

    if record.get("source_type") != "run_raw":
        raise PatcherIntegrityError("postcondition target is not a run_raw record")
    paragraph = paragraph_ancestor(ancestors)
    if paragraph is None:
        raise PatcherIntegrityError("postcondition target lost its paragraph ancestor")

    analysis = resolve_run_formatting(record, paragraph, catalog, DOCUMENT_PART)
    key = _TARGET_KEY[operation.key.property_slot]
    resolved = extract_resolved_value(key, analysis)
    if resolved.status is not ResolutionStatus.RESOLVED:
        raise PatcherIntegrityError(
            f"postcondition Analysis did not resolve the target property: {resolved.status}"
        )
    if key.property_slot == "bold":
        if resolved.value is not operation.desired_value:
            raise PatcherIntegrityError(
                f"postcondition mismatch: current {resolved.value!r} != desired "
                f"{operation.desired_value!r}"
            )
    else:
        desired = operation.desired_value
        current = resolved.value
        if (
            not isinstance(desired, LengthValue)
            or not isinstance(current, Length)
            or current.unit != "pt"
            or current.value != desired.value
        ):
            raise PatcherIntegrityError(
                f"postcondition mismatch: current {current!r} != desired {desired!r}"
            )


def relread_document_xml(package_bytes: bytes) -> bytes:
    """Read word/document.xml back from produced package bytes."""

    with zipfile.ZipFile(io.BytesIO(package_bytes), "r") as zf:
        return zf.read(DOCUMENT_PART)
