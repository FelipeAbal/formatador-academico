"""Patcher v0.1 — OOXML run-property mutation (decision 0028 §§11-16).

Pure lxml tree surgery over the in-memory document tree of
`word/document.xml`. All property counting/location is STRICTLY among
DIRECT CHILDREN of `w:r`/`w:rPr`; the descendant axis is never used for
`w:rPr`, `w:b` or `w:sz`, so nothing inside `w:rPrChange` (or any other
nested container) can be mistaken for a direct target property.

Canonical child order inside `w:rPr` follows the CT_RPr content model
(EG_RPrBase + rPrChange) of ECMA-376 Part 1 (wml.xsd), frozen in
`RPR_CANONICAL_RANK` below.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from lxml import etree

from ..docx_parser import W_NS
from ..operation_plan.model import LengthValue
from .model import PatchReason

MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"

W_P = f"{{{W_NS}}}p"
W_PPR = f"{{{W_NS}}}pPr"
W_JC = f"{{{W_NS}}}jc"
W_R = f"{{{W_NS}}}r"
W_RPR = f"{{{W_NS}}}rPr"
W_B = f"{{{W_NS}}}b"
W_SZ = f"{{{W_NS}}}sz"
W_SZCS = f"{{{W_NS}}}szCs"
W_RPRCHANGE = f"{{{W_NS}}}rPrChange"
W_VAL = f"{{{W_NS}}}val"

PPR_CANONICAL_ORDER: tuple[str, ...] = (
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
    "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorInd",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
    "sectPr", "pPrChange",
)
PPR_CANONICAL_RANK = {f"{{{W_NS}}}{local}": rank for rank, local in enumerate(PPR_CANONICAL_ORDER)}

MC_ALTERNATE_CONTENT = f"{{{MC_NS}}}AlternateContent"

# Canonical CT_RPr child order (EG_RPrBase then rPrChange), verified against
# the ECMA-376 Part 1 transitional schema content model for CT_RPr:
#   <xsd:group ref="EG_RPrBase" minOccurs="0" maxOccurs="unbounded"/>
#   <xsd:element name="rPrChange" type="CT_RPrChange" minOccurs="0"/>
# with EG_RPrBase declaring the elements in exactly the sequence below.
RPR_CANONICAL_ORDER: tuple[str, ...] = (
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps",
    "strike", "dstrike", "outline", "shadow", "emboss", "imprint",
    "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
    "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
    "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
    "eastAsianLayout", "specVanish", "oMath",
    "rPrChange",
)

RPR_CANONICAL_RANK: dict[str, int] = {
    f"{{{W_NS}}}{local}": rank for rank, local in enumerate(RPR_CANONICAL_ORDER)
}

MAX_HALF_POINTS = 3276  # 1638 pt upper bound (decision 0028 §15)


class Reject(Exception):
    """Internal control flow: ordinary rejection with a closed reason."""

    def __init__(self, reason: PatchReason, detail: str):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _qn(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _direct_children(node: etree._Element, tag: str) -> list[etree._Element]:
    """Direct element children with the exact tag — never the descendant axis."""

    return [c for c in node if isinstance(c.tag, str) and c.tag == tag]


def direct_run_properties(run: etree._Element) -> list[etree._Element]:
    """Direct w:rPr children of the run (0, 1 or more — caller validates)."""

    return _direct_children(run, W_RPR)


def _element_children(node: etree._Element) -> list[etree._Element]:
    return [c for c in node if isinstance(c.tag, str)]


def validate_rpr_shape(run: etree._Element, target_tag: str) -> etree._Element | None:
    """Validate the direct run-properties shape (decision 0028 §11/§12).

    Returns the single canonical direct w:rPr to reuse, or None when the run
    has no w:rPr (the caller then creates one as the first child). Raises
    Reject for every noncanonical-but-ordinary shape:
    - more than one direct w:rPr;
    - sole direct w:rPr not the first child of w:r;
    - direct mc:AlternateContent inside rPr;
    - pre-existing rPr element children outside the canonical schema order;
    - more than one direct target property (duplicate_target_property),
      even when the duplicates are lexically identical.

    w:rPrChange content is protected: nested w:rPr/w:b/w:sz inside it are
    never counted here because counting is direct-children-only.
    """

    rprs = direct_run_properties(run)
    if len(rprs) > 1:
        raise Reject(
            PatchReason.NONCANONICAL_RUN_PROPERTIES,
            "more than one direct w:rPr in target run",
        )
    if not rprs:
        return None
    rpr = rprs[0]
    first_element = next((c for c in run if isinstance(c.tag, str)), None)
    if first_element is not rpr:
        raise Reject(
            PatchReason.NONCANONICAL_RUN_PROPERTIES,
            "sole direct w:rPr is not the first child of w:r",
        )
    if _direct_children(rpr, MC_ALTERNATE_CONTENT):
        raise Reject(
            PatchReason.NONCANONICAL_RUN_PROPERTIES,
            "direct mc:AlternateContent inside target w:rPr",
        )
    targets = _direct_children(rpr, target_tag)
    if len(targets) > 1:
        raise Reject(
            PatchReason.DUPLICATE_TARGET_PROPERTY,
            f"more than one direct {_qn('b') if target_tag == W_B else _qn('sz')}",
        )
    ranks = []
    for child in _element_children(rpr):
        rank = RPR_CANONICAL_RANK.get(child.tag)
        if rank is None:
            raise Reject(
                PatchReason.NONCANONICAL_RUN_PROPERTIES,
                f"direct w:rPr child outside the v0.1 canonical rank table: {child.tag}",
            )
        ranks.append(rank)
    if ranks != sorted(ranks):
        raise Reject(
            PatchReason.NONCANONICAL_RUN_PROPERTIES,
            "pre-existing w:rPr children are not in canonical schema order",
        )
    return rpr


def validate_ppr_shape(paragraph: etree._Element, target_tag: str) -> etree._Element | None:
    """Validate direct w:pPr shape and its canonical CT_PPr order."""
    pprs = _direct_children(paragraph, W_PPR)
    if len(pprs) > 1:
        raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, "more than one direct w:pPr")
    if not pprs:
        return None
    ppr = pprs[0]
    first_element = next((c for c in paragraph if isinstance(c.tag, str)), None)
    if first_element is not ppr:
        raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, "sole direct w:pPr is not the first child of w:p")
    if _direct_children(ppr, MC_ALTERNATE_CONTENT):
        raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, "direct mc:AlternateContent inside target w:pPr")
    targets = _direct_children(ppr, target_tag)
    if len(targets) > 1:
        raise Reject(PatchReason.DUPLICATE_TARGET_PROPERTY, "more than one direct w:jc")
    ranks = []
    for child in _element_children(ppr):
        rank = PPR_CANONICAL_RANK.get(child.tag)
        if rank is None:
            raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, f"direct w:pPr child outside canonical rank table: {child.tag}")
        ranks.append(rank)
    if ranks != sorted(ranks):
        raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, "pre-existing w:pPr children are not in canonical schema order")
    return ppr


def ensure_ppr(paragraph: etree._Element, ppr: etree._Element | None) -> etree._Element:
    if ppr is not None:
        return ppr
    ppr = etree.Element(W_PPR)
    paragraph.insert(0, ppr)
    return ppr


def apply_alignment(paragraph: etree._Element, ppr: etree._Element, desired: str) -> None:
    if desired not in {"left", "center", "right", "both"}:
        raise Reject(PatchReason.UNSUPPORTED_OPERATION, f"alignment desired value is not canonical: {desired!r}")
    targets = _direct_children(ppr, W_JC)
    if targets:
        element = targets[0]
        if _element_children(element) or set(element.attrib) - {W_VAL}:
            raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, "direct w:jc is outside the canonical shape")
        if element.get(W_VAL) is None:
            raise Reject(PatchReason.NONCANONICAL_RUN_PROPERTIES, "direct w:jc lacks required w:val")
        element.set(W_VAL, desired)
    else:
        element = etree.Element(W_JC)
        element.set(W_VAL, desired)
        _insert_ppr_canonical(ppr, element)


def _insert_ppr_canonical(ppr: etree._Element, element: etree._Element) -> None:
    rank = PPR_CANONICAL_RANK[element.tag]
    for child in _element_children(ppr):
        if PPR_CANONICAL_RANK[child.tag] > rank:
            child.addprevious(element)
            return
    ppr.append(element)


def ensure_rpr(run: etree._Element, rpr: etree._Element | None) -> etree._Element:
    """Reuse the validated rPr or create exactly one as the first child."""

    if rpr is not None:
        return rpr
    rpr = etree.Element(W_RPR)
    run.insert(0, rpr)
    return rpr


def _insert_canonical(rpr: etree._Element, element: etree._Element) -> None:
    """Insert at the canonical schema position without moving any sibling.

    Rule (decision 0028 §13): insert immediately before the first existing
    direct child whose canonical rank is greater; otherwise append (the rank
    table places rPrChange last, so 'before rPrChange' falls out naturally).
    """

    rank = RPR_CANONICAL_RANK[element.tag]
    for child in _element_children(rpr):
        if RPR_CANONICAL_RANK[child.tag] > rank:
            child.addprevious(element)
            return
    rpr.append(element)


class BoldValue(Enum):
    TRUE = True
    FALSE = False


def apply_bold(run: etree._Element, rpr: etree._Element, desired: bool) -> None:
    """Realize one canonical direct w:b (decision 0028 §14).

    true  -> exactly one direct <w:b/> (no attributes, no children);
    false -> exactly one direct <w:b w:val="0"/> — never a removal, so
             inherited/toggled bold from the cascade is defeated.
    Only the target element is normalized; no other property is touched.
    """

    if not isinstance(desired, bool):
        raise Reject(
            PatchReason.UNSUPPORTED_OPERATION,
            f"bold desired value must be bool, got {type(desired).__name__}",
        )
    targets = _direct_children(rpr, W_B)
    if targets:
        element = targets[0]
        if _element_children(element):
            raise Reject(
                PatchReason.NONCANONICAL_RUN_PROPERTIES,
                "direct w:b with element children is outside the v0.1 canonical shape",
            )
        element.attrib.clear()
        if not desired:
            element.set(W_VAL, "0")
    else:
        element = etree.Element(W_B)
        if not desired:
            element.set(W_VAL, "0")
        _insert_canonical(rpr, element)


def _exact_half_points(points: Decimal) -> int:
    """Return exact half-points without context rounding or huge exponent work."""

    sign, digits, exponent = points.as_tuple()
    if sign:
        raise Reject(PatchReason.UNREPRESENTABLE_VALUE, "font_size must be strictly positive")

    # Any positive exponent above 3 is already beyond 3276 half-points even
    # for the smallest positive coefficient. Reject before constructing 10**N.
    if exponent > 3:
        raise Reject(
            PatchReason.UNREPRESENTABLE_VALUE,
            f"font_size exceeds the v0.1 bound of {MAX_HALF_POINTS} half-points",
        )

    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    numerator = coefficient * 2

    if exponent >= 0:
        half_points = numerator * (10 ** exponent)
    else:
        scale = -exponent
        # `numerator` has at most len(digits)+1 decimal digits. If the scale
        # is larger, a positive numerator cannot be divisible by 10**scale;
        # reject before allocating an enormous power of ten.
        if scale > len(digits) + 1:
            raise Reject(
                PatchReason.UNREPRESENTABLE_VALUE,
                "font_size is not exactly representable in half-points (no rounding)",
            )
        denominator = 10 ** scale
        if numerator % denominator:
            raise Reject(
                PatchReason.UNREPRESENTABLE_VALUE,
                "font_size is not exactly representable in half-points (no rounding)",
            )
        half_points = numerator // denominator

    if half_points > MAX_HALF_POINTS:
        raise Reject(
            PatchReason.UNREPRESENTABLE_VALUE,
            f"font_size exceeds the v0.1 bound of {MAX_HALF_POINTS} half-points",
        )
    return half_points


def half_points_lexical(desired: LengthValue) -> str:
    """Convert a semantic pt length into the canonical w:sz lexical value.

    Decimal-only semantics (decision 0028 §15): unit exactly 'pt', finite,
    strictly positive, points*2 an exact integer (no rounding), at most
    3276 half-points, canonical base-10 integer without leading zeroes.
    Anything else is an ordinary `unrepresentable_value` rejection.
    """

    if not isinstance(desired, LengthValue):
        raise Reject(
            PatchReason.UNSUPPORTED_OPERATION,
            f"font_size desired value must be LengthValue, got {type(desired).__name__}",
        )
    if desired.unit != "pt":
        raise Reject(PatchReason.UNREPRESENTABLE_VALUE, "font_size unit must be 'pt'")
    points = desired.value
    if not points.is_finite():
        raise Reject(PatchReason.UNREPRESENTABLE_VALUE, "font_size must be finite")
    if points <= 0:
        raise Reject(PatchReason.UNREPRESENTABLE_VALUE, "font_size must be strictly positive")
    half_points = _exact_half_points(points)
    return str(half_points)


def apply_font_size(run: etree._Element, rpr: etree._Element, desired: LengthValue) -> None:
    """Realize one canonical direct w:sz (decision 0028 §15).

    Changes only the `w:val` of an existing direct w:sz, or creates one at
    its canonical schema position. `w:szCs` is a deliberate v0.1 blind spot
    and is never touched (production-blocking debt, decision 0028 §27).
    """

    lexical = half_points_lexical(desired)
    targets = _direct_children(rpr, W_SZ)
    if targets:
        element = targets[0]
        if set(element.attrib) - {W_VAL} or _element_children(element):
            raise Reject(
                PatchReason.NONCANONICAL_RUN_PROPERTIES,
                "direct w:sz carries attributes/children outside CT_HpsMeasure",
            )
        element.set(W_VAL, lexical)
    else:
        element = etree.Element(W_SZ)
        element.set(W_VAL, lexical)
        _insert_canonical(rpr, element)


def mutate_paragraph(paragraph: etree._Element, property_slot: str, desired) -> None:
    if property_slot != "alignment":
        raise Reject(PatchReason.UNSUPPORTED_OPERATION, f"unsupported paragraph property: {property_slot}")
    ppr = validate_ppr_shape(paragraph, W_JC)
    ppr = ensure_ppr(paragraph, ppr)
    apply_alignment(paragraph, ppr, desired)


def mutate_run(run: etree._Element, property_slot: str, desired) -> None:
    """Validate shape, then apply the single authorized mutation."""

    target_tag = {"bold": W_B, "font_size": W_SZ}[property_slot]
    rpr = validate_rpr_shape(run, target_tag)
    rpr = ensure_rpr(run, rpr)
    if property_slot == "bold":
        apply_bold(run, rpr, desired)
    else:
        apply_font_size(run, rpr, desired)
