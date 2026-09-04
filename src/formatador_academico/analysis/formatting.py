"""Formatting Resolution engine — Analysis View v0.1b, Marco 1 (non-toggle).

Implements the cascade of decision 0015 for paragraph properties (jc, spacing,
indents with the numbering clause) and non-toggle run properties (sz, rFonts
slots, lang slots, underline, vertAlign). Toggle properties (w:b, w:i) are
Marco 2 and are NOT implemented here.

Never raises for bad document content: failure unit is (target, property).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from .formatting_model import (
    R_AUTOSPACING,
    R_NUMBERING_INDENT,
    R_STYLE_CYCLE,
    R_STYLES_UNAVAILABLE,
    R_UNSUPPORTED_UNIT,
    W_DUPLICATE_PROPERTY,
    W_INVALID_VALUE,
    W_MISSING_STYLE,
    W_NUMBERING_PRESENT,
    W_STYLE_CYCLE,
    W_WRONG_STYLE_TYPE,
    FontSpec,
    FormattingEvidence,
    IndentSpec,
    LanguageSpec,
    Length,
    LevelEvidence,
    LineSpacing,
    ResolvedParagraphFormatting,
    ResolvedRunFormatting,
    ResolvedValue,
    ResolutionStatus,
    SpacingSpec,
    StyleCatalog,
    StyleEntry,
    ThemeRef,
)
from .model import AnalysisWarning
from .property_bag import bag_from_properties_raw
from .style_catalog import default_styles, find_styles

_TRUE_TOKENS = {"1", "true", "on"}


class _InvalidLexical(Exception):
    pass


@dataclass(frozen=True)
class _Level:
    name: str  # "direct" | "character_style" | "paragraph_style" | "doc_defaults"
    source_kind: str  # "direct" | "style" | "doc_defaults"
    part: str
    style_id: str | None
    bag: Any  # RawPropertyBag | None
    blocked: str | None = None  # e.g. R_STYLES_UNAVAILABLE
    ambiguous_candidates: tuple[StyleEntry, ...] = ()


def _attr(prop, name: str) -> str | None:
    for k, v in prop.raw_attrs:
        if k == name:
            return v
    return None


def _truthy(value: str | None) -> bool:
    return value is not None and value.lower() in _TRUE_TOKENS


def _int_lexical(raw: str | None) -> int:
    if raw is None:
        raise _InvalidLexical()
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        raise _InvalidLexical() from None


def _evidence(level: _Level, prop, raw_value: str | None) -> FormattingEvidence:
    return FormattingEvidence(
        source_kind=level.source_kind,
        part=level.part,
        structural_path=prop.structural_path,
        style_id=level.style_id,
        property_name=prop.property_name,
        raw_value=raw_value,
    )


def _warn(warnings: list[AnalysisWarning], code: str, message: str, path: str) -> None:
    warnings.append(AnalysisWarning(code=code, message=message, structural_path=path))


def _ambiguous_level(chain: list[LevelEvidence], level: _Level,
                     prop_name: str) -> ResolvedValue:
    for cand in level.ambiguous_candidates:
        chain.append(LevelEvidence(
            level=level.name, declared=True,
            detail="ambiguous_duplicate_style_id",
            evidence=FormattingEvidence(
                source_kind="style", part=level.part,
                structural_path=cand.structural_path,
                style_id=cand.style_id, property_name=prop_name, raw_value=None,
            ),
        ))
    return ResolvedValue(ResolutionStatus.AMBIGUOUS, None, None, tuple(chain), None)


def _cascade(
    levels: tuple[_Level, ...],
    prop_name: str,
    convert: Callable[[Any], Any],
    warnings: list[AnalysisWarning],
    raw_of: Callable[[Any], str | None],
    declares: Callable[[Any], bool],
) -> ResolvedValue:
    """Generic first-valid-declaration cascade for non-toggle properties.

    `declares` filters, inside a property element, whether THIS slot is
    declared (matters for multi-attribute elements like w:rFonts / w:lang).
    Duplicates are compared per slot value.
    """
    chain: list[LevelEvidence] = []
    for level in levels:
        if level.ambiguous_candidates:
            return _ambiguous_level(chain, level, prop_name)
        if level.blocked is not None:
            chain.append(LevelEvidence(level.name, False, level.blocked, None))
            return ResolvedValue(
                ResolutionStatus.UNRESOLVED, None, None, tuple(chain), level.blocked
            )
        props = [] if level.bag is None else [
            e for e in level.bag.entries
            if e.property_name == prop_name and declares(e)
        ]
        if not props:
            chain.append(LevelEvidence(level.name, False, "not_declared", None))
            continue
        chosen = props[0]
        if len(props) > 1:
            values = {raw_of(p) for p in props}
            if len(values) == 1:
                _warn(warnings, W_DUPLICATE_PROPERTY,
                      f"Duplicate property {prop_name} with identical slot value; first used.",
                      props[1].structural_path)
            else:
                for p in props:
                    chain.append(LevelEvidence(level.name, True, "duplicate_conflict",
                                               _evidence(level, p, raw_of(p))))
                _warn(warnings, W_DUPLICATE_PROPERTY,
                      f"Duplicate property {prop_name} with conflicting values.",
                      props[1].structural_path)
                return ResolvedValue(ResolutionStatus.AMBIGUOUS, None, None, tuple(chain), None)
        raw_value = raw_of(chosen)
        ev = _evidence(level, chosen, raw_value)
        try:
            value = convert(chosen)
        except _InvalidLexical:
            chain.append(LevelEvidence(level.name, True, "invalid", ev))
            _warn(warnings, W_INVALID_VALUE,
                  f"Invalid lexical value for {prop_name}: {raw_value!r}.",
                  chosen.structural_path)
            return ResolvedValue(ResolutionStatus.INVALID, None, None, tuple(chain), None)
        chain.append(LevelEvidence(level.name, True, "declared", ev))
        return ResolvedValue(ResolutionStatus.RESOLVED, value, ev, tuple(chain), None)
    return ResolvedValue(ResolutionStatus.ABSENT, None, None, tuple(chain), None)


# ---------------------------------------------------------------------------
# Style chain walking (iterative, visited set, contract policies)
# ---------------------------------------------------------------------------

def _style_chain_levels(
    catalog: StyleCatalog,
    start: StyleEntry,
    expected_type: str,
    level_name: str,
    bag_kind: str,  # "ppr_bag" | "rpr_bag"
    warnings: list[AnalysisWarning],
) -> list[_Level]:
    """Walk start -> basedOn ancestors (most specific first).

    Cycle members are excluded; the prefix before the cycle remains usable and
    the chain ends with a blocked level (R_STYLE_CYCLE) so dependent
    properties degrade to unresolved(style_cycle) — decision 0015.
    """
    levels: list[_Level] = []
    visited: list[str] = []
    current: StyleEntry | None = start
    while current is not None:
        if current.style_id in visited:
            first = visited.index(current.style_id)
            del levels[first:]
            _warn(warnings, W_STYLE_CYCLE,
                  f"basedOn cycle detected at style {current.style_id!r}; cycle members excluded.",
                  current.structural_path)
            levels.append(_Level(level_name, "style", catalog.part_name,
                                 current.style_id, None, blocked=R_STYLE_CYCLE))
            return levels
        visited.append(current.style_id)
        levels.append(_Level(
            name=level_name, source_kind="style", part=catalog.part_name,
            style_id=current.style_id,
            bag=getattr(current, bag_kind),
        ))
        parent_id = current.based_on_id
        if not parent_id:
            break
        candidates = find_styles(catalog, parent_id)
        if not candidates:
            _warn(warnings, W_MISSING_STYLE,
                  f"basedOn parent {parent_id!r} not found; style {current.style_id!r} treated as chain root.",
                  current.structural_path)
            break
        if len(candidates) > 1:
            levels.append(_Level(
                name=level_name, source_kind="style", part=catalog.part_name,
                style_id=parent_id, bag=None, ambiguous_candidates=candidates,
            ))
            break
        parent = candidates[0]
        if parent.style_type != expected_type:
            _warn(warnings, W_WRONG_STYLE_TYPE,
                  f"basedOn parent {parent_id!r} has type {parent.style_type!r}, expected {expected_type!r}; ignored.",
                  current.structural_path)
            break
        current = parent
    return levels


def _resolve_start_style(
    catalog: StyleCatalog,
    style_id: str | None,
    expected_type: str,
    level_name: str,
    bag_kind: str,
    warnings: list[AnalysisWarning],
    use_default: bool,
    anchor_path: str,
) -> list[_Level]:
    """Resolve a starting style reference into cascade levels.

    Policies (decision 0015): missing/wrong-type references are ignored with a
    warning (never unresolved by themselves); duplicate ids relevant to the
    resolution become an ambiguous marker level.
    """
    if catalog.part_status == "unreadable":
        return [_Level(level_name, "style", catalog.part_name, None, None,
                       blocked=R_STYLES_UNAVAILABLE)]
    start: StyleEntry | None = None
    if style_id is not None:
        candidates = find_styles(catalog, style_id)
        if not candidates:
            _warn(warnings, W_MISSING_STYLE,
                  f"Referenced style {style_id!r} not found; reference ignored.",
                  anchor_path)
            return []
        if len(candidates) > 1:
            return [_Level(level_name, "style", catalog.part_name, style_id, None,
                           ambiguous_candidates=candidates)]
        start = candidates[0]
        if start.style_type != expected_type:
            _warn(warnings, W_WRONG_STYLE_TYPE,
                  f"Referenced style {style_id!r} has type {start.style_type!r}, expected {expected_type!r}; ignored.",
                  anchor_path)
            return []
    elif use_default:
        defaults = default_styles(catalog, expected_type)
        if len(defaults) > 1:
            return [_Level(level_name, "style", catalog.part_name, None, None,
                           ambiguous_candidates=defaults)]
        if defaults:
            start = defaults[0]
    if start is None:
        return []
    return _style_chain_levels(catalog, start, expected_type, level_name, bag_kind, warnings)


def _doc_defaults_level(catalog: StyleCatalog, bag_kind: str) -> _Level:
    if catalog.part_status == "unreadable":
        return _Level("doc_defaults", "doc_defaults", catalog.part_name, None, None,
                      blocked=R_STYLES_UNAVAILABLE)
    bag = None
    if catalog.doc_defaults is not None:
        bag = getattr(catalog.doc_defaults, bag_kind)
    return _Level("doc_defaults", "doc_defaults", catalog.part_name, None, bag)


def _bag_of(record: dict[str, Any] | None) -> Any:
    if record is None:
        return None
    return bag_from_properties_raw(record.get("properties_raw"))


def _style_ref_id(bag: Any, prop_name: str) -> str | None:
    if bag is None:
        return None
    for e in bag.entries:
        if e.property_name == prop_name:
            return _attr(e, "w:val")
    return None


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

def _conv_font_size(prop) -> Length:
    raw = _attr(prop, "w:val")
    half = _int_lexical(raw)
    if half < 0:
        raise _InvalidLexical()
    return Length(value=Decimal(half) / 2, unit="pt", raw_value=raw, raw_unit="half_point")


def _conv_twips(attr: str) -> Callable[[Any], Length]:
    def convert(prop) -> Length:
        raw = _attr(prop, attr)
        twips = _int_lexical(raw)
        return Length(value=Decimal(twips) / 20, unit="pt", raw_value=raw, raw_unit="twip")
    return convert


def _conv_hundredths_of_line(attr: str) -> Callable[[Any], Decimal]:
    def convert(prop) -> Decimal:
        raw = _attr(prop, attr)
        value = _int_lexical(raw)
        return Decimal(value) / 100
    return convert


def _conv_line_spacing(prop) -> LineSpacing:
    raw_line = _attr(prop, "w:line")
    raw_rule = _attr(prop, "w:lineRule")
    rule = raw_rule or "auto"
    if raw_line is None:
        return LineSpacing(rule=rule, value=None, unit=None, raw_line=None, raw_rule=raw_rule)
    line = _int_lexical(raw_line)
    if rule == "auto":
        return LineSpacing(rule=rule, value=Decimal(line) / 240, unit="multiple",
                           raw_line=raw_line, raw_rule=raw_rule)
    if rule in ("atLeast", "exact"):
        return LineSpacing(rule=rule, value=Decimal(line) / 20, unit="pt",
                           raw_line=raw_line, raw_rule=raw_rule)
    # Unknown lineRule: preserve lexically without numeric normalization.
    return LineSpacing(rule=rule, value=None, unit=None, raw_line=raw_line, raw_rule=raw_rule)


def _conv_token(prop) -> str:
    raw = _attr(prop, "w:val")
    if raw is None:
        raise _InvalidLexical()
    return raw


def _conv_underline(prop) -> str:
    return _attr(prop, "w:val") or "single"


def _conv_slot_attr(attr: str) -> Callable[[Any], str]:
    def convert(prop) -> str:
        raw = _attr(prop, attr)
        if raw is None:
            raise _InvalidLexical()
        return raw
    return convert


def _conv_font_slot(attr: str, theme: bool) -> Callable[[Any], Any]:
    def convert(prop) -> Any:
        raw = _attr(prop, attr)
        if raw is None:
            raise _InvalidLexical()
        return ThemeRef(theme_slot=raw) if theme else raw
    return convert


def _declares_attr(attr: str) -> Callable[[Any], bool]:
    return lambda prop: _attr(prop, attr) is not None


def _declares_any(*attrs: str) -> Callable[[Any], bool]:
    return lambda prop: any(_attr(prop, a) is not None for a in attrs)


def _always(prop) -> bool:
    return True


# ---------------------------------------------------------------------------
# Paragraph formatting
# ---------------------------------------------------------------------------

_INDENT_SLOTS = (
    ("left", "w:left", "w:leftChars"),
    ("right", "w:right", "w:rightChars"),
    ("start", "w:start", "w:startChars"),
    ("end", "w:end", "w:endChars"),
    ("first_line", "w:firstLine", "w:firstLineChars"),
    ("hanging", "w:hanging", "w:hangingChars"),
)


def _has_property(bag: Any, prop_name: str) -> bool:
    return bag is not None and any(e.property_name == prop_name for e in bag.entries)


def _ind_declaring(bag: Any, attr: str, chars_attr: str) -> list:
    if bag is None:
        return []
    return [
        e for e in bag.entries
        if e.property_name == "w:ind"
        and (_attr(e, attr) is not None or _attr(e, chars_attr) is not None)
    ]


def _resolve_indent_slot(
    slot: str,
    attr: str,
    chars_attr: str,
    levels: tuple[_Level, ...],
    numbering_relevant: bool,
    part: str,
    warnings: list[AnalysisWarning],
) -> ResolvedValue:
    """Numbering-aware indent slot resolution (decision 0015, cases A/B/C).

    Levels are (direct, *style_chain, doc_defaults). Numbering sits between
    the style chain and docDefaults: if numPr is relevant and neither direct
    nor style declared the slot, the slot degrades to
    unresolved(numbering_indent_unsupported) before docDefaults is consulted.
    """
    chain: list[LevelEvidence] = []
    doc_defaults = levels[-1]
    for level in levels:
        if level is doc_defaults and numbering_relevant:
            _warn(warnings, W_NUMBERING_PRESENT,
                  f"Indent slot {slot} may depend on numbering.xml (numPr present), "
                  "which is out of scope for v0.1b Marco 1.",
                  part)
            return ResolvedValue(ResolutionStatus.UNRESOLVED, None, None,
                                 tuple(chain), R_NUMBERING_INDENT)
        if level.ambiguous_candidates:
            return _ambiguous_level(chain, level, "w:ind")
        if level.blocked is not None:
            chain.append(LevelEvidence(level.name, False, level.blocked, None))
            return ResolvedValue(ResolutionStatus.UNRESOLVED, None, None,
                                 tuple(chain), level.blocked)
        inds = _ind_declaring(level.bag, attr, chars_attr)
        if not inds:
            chain.append(LevelEvidence(level.name, False, "not_declared", None))
            continue
        chosen = inds[0]
        if len(inds) > 1:
            values = {(_attr(p, attr), _attr(p, chars_attr)) for p in inds}
            if len(values) == 1:
                _warn(warnings, W_DUPLICATE_PROPERTY,
                      f"Duplicate w:ind with identical {attr} value; first used.",
                      inds[1].structural_path)
            else:
                for p in inds:
                    chain.append(LevelEvidence(level.name, True, "duplicate_conflict",
                                               _evidence(level, p, _attr(p, attr)
                                                         or _attr(p, chars_attr))))
                _warn(warnings, W_DUPLICATE_PROPERTY,
                      "Duplicate w:ind with conflicting values.",
                      inds[1].structural_path)
                return ResolvedValue(ResolutionStatus.AMBIGUOUS, None, None, tuple(chain), None)
        ev = _evidence(level, chosen, _attr(chosen, attr) or _attr(chosen, chars_attr))
        if _attr(chosen, attr) is None:
            chain.append(LevelEvidence(level.name, True, "unsupported_unit", ev))
            return ResolvedValue(ResolutionStatus.UNRESOLVED, None, None,
                                 tuple(chain), R_UNSUPPORTED_UNIT)
        try:
            value = _conv_twips(attr)(chosen)
        except _InvalidLexical:
            chain.append(LevelEvidence(level.name, True, "invalid", ev))
            _warn(warnings, W_INVALID_VALUE,
                  f"Invalid lexical value for w:ind {attr}: {_attr(chosen, attr)!r}.",
                  chosen.structural_path)
            return ResolvedValue(ResolutionStatus.INVALID, None, None, tuple(chain), None)
        chain.append(LevelEvidence(level.name, True, "declared", ev))
        return ResolvedValue(ResolutionStatus.RESOLVED, value, ev, tuple(chain), None)
    return ResolvedValue(ResolutionStatus.ABSENT, None, None, tuple(chain), None)


def _resolve_spacing_slot(
    slot_attrs: tuple[str, ...],
    auto_attr: str | None,
    convert: Callable[[Any], Any],
    raw_of: Callable[[Any], str | None],
    levels: tuple[_Level, ...],
    warnings: list[AnalysisWarning],
) -> ResolvedValue:
    """Spacing slot cascade with per-level autospacing degradation."""
    chain: list[LevelEvidence] = []
    for level in levels:
        if level.ambiguous_candidates:
            return _ambiguous_level(chain, level, "w:spacing")
        if level.blocked is not None:
            chain.append(LevelEvidence(level.name, False, level.blocked, None))
            return ResolvedValue(ResolutionStatus.UNRESOLVED, None, None,
                                 tuple(chain), level.blocked)
        spacings = [] if level.bag is None else [
            e for e in level.bag.entries if e.property_name == "w:spacing"
        ]
        target = None
        for sp in spacings:
            if any(_attr(sp, a) is not None for a in slot_attrs):
                target = sp
                break
        if target is None and auto_attr is not None:
            for sp in spacings:
                if _truthy(_attr(sp, auto_attr)):
                    chain.append(LevelEvidence(
                        level.name, True, "autospacing",
                        _evidence(level, sp, _attr(sp, auto_attr))))
                    return ResolvedValue(ResolutionStatus.UNRESOLVED, None, None,
                                         tuple(chain), R_AUTOSPACING)
        if target is None:
            chain.append(LevelEvidence(level.name, False, "not_declared", None))
            continue
        ev = _evidence(level, target, raw_of(target))
        try:
            value = convert(target)
        except _InvalidLexical:
            chain.append(LevelEvidence(level.name, True, "invalid", ev))
            _warn(warnings, W_INVALID_VALUE,
                  f"Invalid lexical value for w:spacing {slot_attrs[0]}: {raw_of(target)!r}.",
                  target.structural_path)
            return ResolvedValue(ResolutionStatus.INVALID, None, None, tuple(chain), None)
        chain.append(LevelEvidence(level.name, True, "declared", ev))
        return ResolvedValue(ResolutionStatus.RESOLVED, value, ev, tuple(chain), None)
    return ResolvedValue(ResolutionStatus.ABSENT, None, None, tuple(chain), None)


def _dedupe_warnings(warnings: list[AnalysisWarning]) -> tuple[AnalysisWarning, ...]:
    seen: set[tuple[str, str, str]] = set()
    out: list[AnalysisWarning] = []
    for w in warnings:
        key = (w.code, w.message, w.structural_path)
        if key not in seen:
            seen.add(key)
            out.append(w)
    return tuple(out)


def resolve_paragraph_formatting(
    paragraph: dict[str, Any],
    catalog: StyleCatalog,
    part: str,
) -> ResolvedParagraphFormatting:
    if paragraph.get("source_type") != "paragraph":
        raise ValueError("resolve_paragraph_formatting requires a PhysicalIR paragraph record")
    if not paragraph.get("structural_path") or not paragraph.get("physical_hash"):
        raise ValueError("paragraph lacks provenance required by Analysis View")

    warnings: list[AnalysisWarning] = []
    direct_bag = _bag_of(paragraph)
    anchor = paragraph["structural_path"]

    # pStyle id: documental fact from the direct bag only (no cascade).
    direct_level = _Level("direct", "direct", part, None, direct_bag)
    paragraph_style_id = _cascade(
        (direct_level,), "w:pStyle", _conv_token, warnings,
        raw_of=lambda p: _attr(p, "w:val"), declares=_always,
    )
    pstyle_id = paragraph_style_id.value if (
        paragraph_style_id.status is ResolutionStatus.RESOLVED
    ) else None

    style_levels = _resolve_start_style(
        catalog, pstyle_id, "paragraph", "paragraph_style", "ppr_bag",
        warnings, use_default=True, anchor_path=anchor,
    )
    doc_defaults = _doc_defaults_level(catalog, "ppr_bag")

    all_levels = (direct_level, *style_levels, doc_defaults)

    alignment = _cascade(all_levels, "w:jc", _conv_token, warnings,
                         raw_of=lambda p: _attr(p, "w:val"), declares=_always)

    spacing = SpacingSpec(
        before=_resolve_spacing_slot(("w:before",), "w:beforeAutospacing",
                                     _conv_twips("w:before"),
                                     lambda p: _attr(p, "w:before"), all_levels, warnings),
        after=_resolve_spacing_slot(("w:after",), "w:afterAutospacing",
                                    _conv_twips("w:after"),
                                    lambda p: _attr(p, "w:after"), all_levels, warnings),
        before_lines=_resolve_spacing_slot(("w:beforeLines",), None,
                                           _conv_hundredths_of_line("w:beforeLines"),
                                           lambda p: _attr(p, "w:beforeLines"),
                                           all_levels, warnings),
        after_lines=_resolve_spacing_slot(("w:afterLines",), None,
                                          _conv_hundredths_of_line("w:afterLines"),
                                          lambda p: _attr(p, "w:afterLines"),
                                          all_levels, warnings),
        line=_resolve_spacing_slot(("w:line", "w:lineRule"), None, _conv_line_spacing,
                                   lambda p: _attr(p, "w:line") or _attr(p, "w:lineRule"),
                                   all_levels, warnings),
    )

    # Numbering relevance: numPr in direct pPr or in any paragraph style chain pPr.
    numbering_relevant = _has_property(direct_bag, "w:numPr") or any(
        _has_property(level.bag, "w:numPr") for level in style_levels
    )

    indents = IndentSpec(**{
        slot: _resolve_indent_slot(slot, attr, chars_attr, all_levels,
                                   numbering_relevant, part, warnings)
        for slot, attr, chars_attr in _INDENT_SLOTS
    })

    return ResolvedParagraphFormatting(
        paragraph_path=paragraph["structural_path"],
        paragraph_hash=paragraph["physical_hash"],
        paragraph_style_id=paragraph_style_id,
        alignment=alignment,
        spacing=spacing,
        indents=indents,
        analysis_warnings=_dedupe_warnings(warnings),
    )


# ---------------------------------------------------------------------------
# Run formatting (non-toggle)
# ---------------------------------------------------------------------------

_FONT_SLOTS = (
    ("ascii", "w:ascii", False),
    ("h_ansi", "w:hAnsi", False),
    ("east_asia", "w:eastAsia", False),
    ("cs", "w:cs", False),
    ("ascii_theme", "w:asciiTheme", True),
    ("h_ansi_theme", "w:hAnsiTheme", True),
    ("east_asia_theme", "w:eastAsiaTheme", True),
    ("cs_theme", "w:cstheme", True),
)

_LANG_SLOTS = (
    ("val", "w:val"),
    ("east_asia", "w:eastAsia"),
    ("bidi", "w:bidi"),
)


def resolve_run_formatting(
    run: dict[str, Any],
    paragraph: dict[str, Any],
    catalog: StyleCatalog,
    part: str,
) -> ResolvedRunFormatting:
    if run.get("source_type") != "run_raw":
        raise ValueError("resolve_run_formatting requires a PhysicalIR run_raw record")
    if paragraph.get("source_type") != "paragraph":
        raise ValueError("paragraph context must be a PhysicalIR paragraph record")
    if not run.get("structural_path") or not run.get("physical_hash"):
        raise ValueError("run lacks provenance required by Analysis View")

    warnings: list[AnalysisWarning] = []
    direct_bag = _bag_of(run)
    anchor = run["structural_path"]

    paragraph_direct_bag = _bag_of(paragraph)
    pstyle_id = _style_ref_id(paragraph_direct_bag, "w:pStyle")
    rstyle_id = _style_ref_id(direct_bag, "w:rStyle")

    char_levels = _resolve_start_style(
        catalog, rstyle_id, "character", "character_style", "rpr_bag",
        warnings, use_default=False, anchor_path=anchor,
    )
    para_levels = _resolve_start_style(
        catalog, pstyle_id, "paragraph", "paragraph_style", "rpr_bag",
        warnings, use_default=True, anchor_path=anchor,
    )
    doc_defaults = _doc_defaults_level(catalog, "rpr_bag")

    all_levels = (
        _Level("direct", "direct", part, None, direct_bag),
        *char_levels,
        *para_levels,
        doc_defaults,
    )

    font_size = _cascade(all_levels, "w:sz", _conv_font_size, warnings,
                         raw_of=lambda p: _attr(p, "w:val"), declares=_always)

    font_spec = FontSpec(**{
        field: _cascade(all_levels, "w:rFonts", _conv_font_slot(attr, theme), warnings,
                        raw_of=lambda p, a=attr: _attr(p, a),
                        declares=_declares_attr(attr))
        for field, attr, theme in _FONT_SLOTS
    })

    language = LanguageSpec(**{
        field: _cascade(all_levels, "w:lang", _conv_slot_attr(attr), warnings,
                        raw_of=lambda p, a=attr: _attr(p, a),
                        declares=_declares_attr(attr))
        for field, attr in _LANG_SLOTS
    })

    underline = _cascade(all_levels, "w:u", _conv_underline, warnings,
                         raw_of=lambda p: _attr(p, "w:val") or "single",
                         declares=_always)
    vert_align = _cascade(all_levels, "w:vertAlign", _conv_token, warnings,
                          raw_of=lambda p: _attr(p, "w:val"), declares=_always)

    return ResolvedRunFormatting(
        run_path=run["structural_path"],
        run_hash=run["physical_hash"],
        font_size=font_size,
        font_spec=font_spec,
        language=language,
        underline=underline,
        vert_align=vert_align,
        analysis_warnings=_dedupe_warnings(warnings),
    )
