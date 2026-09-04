"""Formatting Resolution engine — Analysis View v0.1b, Marco 2.

Implements the frozen Marco 1 cascade plus w:b / w:i toggle resolution.
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
_FALSE_TOKENS = {"0", "false", "off"}


class _InvalidLexical(Exception):
    pass


@dataclass(frozen=True)
class _Level:
    name: str
    source_kind: str
    part: str
    style_id: str | None
    bag: Any
    blocked: str | None = None
    detail_override: str | None = None


def _attr(prop, name: str) -> str | None:
    for k, v in prop.raw_attrs:
        if k == name:
            return v
    return None


def _attr_present(prop, name: str) -> tuple[bool, str | None]:
    for k, v in prop.raw_attrs:
        if k == name:
            return True, v
    return False, None


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


def _cascade(
    levels: tuple[_Level, ...], prop_name: str, convert: Callable[[Any], Any],
    warnings: list[AnalysisWarning], raw_of: Callable[[Any], str | None],
    declares: Callable[[Any], bool],
) -> ResolvedValue:
    chain: list[LevelEvidence] = []
    for level in levels:
        if level.blocked is not None:
            chain.append(LevelEvidence(level.name, False, level.blocked, None))
            return ResolvedValue(ResolutionStatus.UNRESOLVED, None, None, tuple(chain), level.blocked)
        props = [] if level.bag is None else [e for e in level.bag.entries if e.property_name == prop_name and declares(e)]
        if not props:
            chain.append(LevelEvidence(level.name, False, "not_declared", None))
            continue
        chosen = props[0]
        if len(props) > 1:
            values = {raw_of(p) for p in props}
            if len(values) == 1:
                _warn(warnings, W_DUPLICATE_PROPERTY, f"Duplicate property {prop_name} with identical slot value; first used.", props[1].structural_path)
            else:
                for p in props:
                    chain.append(LevelEvidence(level.name, True, "duplicate_conflict", _evidence(level, p, raw_of(p))))
                _warn(warnings, W_DUPLICATE_PROPERTY, f"Duplicate property {prop_name} with conflicting values.", props[1].structural_path)
                return ResolvedValue(ResolutionStatus.AMBIGUOUS, None, None, tuple(chain), None)
        raw_value = raw_of(chosen)
        ev = _evidence(level, chosen, raw_value)
        try:
            value = convert(chosen)
        except _InvalidLexical:
            chain.append(LevelEvidence(level.name, True, "invalid", ev))
            _warn(warnings, W_INVALID_VALUE, f"Invalid lexical value for {prop_name}: {raw_value!r}.", chosen.structural_path)
            return ResolvedValue(ResolutionStatus.INVALID, None, None, tuple(chain), None)
        chain.append(LevelEvidence(level.name, True, level.detail_override or "declared", ev))
        return ResolvedValue(ResolutionStatus.RESOLVED, value, ev, tuple(chain), None)
    return ResolvedValue(ResolutionStatus.ABSENT, None, None, tuple(chain), None)


def _style_chain_levels(catalog: StyleCatalog, start: StyleEntry, expected_type: str,
                        level_name: str, bag_kind: str, warnings: list[AnalysisWarning],
                        start_note: str | None = None) -> list[_Level]:
    levels: list[_Level] = []
    visited: list[str | None] = []
    current: StyleEntry | None = start
    pending_note = start_note
    while current is not None:
        if current.style_id is not None and current.style_id in visited:
            first = visited.index(current.style_id)
            del levels[first:]
            _warn(warnings, W_STYLE_CYCLE, f"basedOn cycle detected at style {current.style_id!r}; cycle members excluded.", current.structural_path)
            levels.append(_Level(level_name, "style", catalog.part_name, current.style_id, None, blocked=R_STYLE_CYCLE))
            return levels
        visited.append(current.style_id)
        levels.append(_Level(level_name, "style", catalog.part_name, current.style_id,
                             getattr(current, bag_kind), detail_override=pending_note))
        pending_note = None
        parent_id = current.based_on_id
        if not parent_id:
            break
        candidates = find_styles(catalog, parent_id)
        if not candidates:
            _warn(warnings, W_MISSING_STYLE, f"basedOn parent {parent_id!r} not found; style {current.style_id!r} treated as chain root.", current.structural_path)
            break
        parent = candidates[0]
        if len(candidates) > 1:
            pending_note = "duplicate_style_id_first_definition"
        if parent.style_type != expected_type:
            _warn(warnings, W_WRONG_STYLE_TYPE, f"basedOn parent {parent_id!r} has type {parent.style_type!r}, expected {expected_type!r}; ignored.", current.structural_path)
            break
        current = parent
    return levels
