"""Analysis View v0.1b — Formatting Resolution View: public models (Marco 1).

Contract: docs/decisions/0015-analysis-v01b-formatting-resolution-contract.md

All structures are immutable, serializable, deterministic and hold no live
lxml objects. The v0.1b never mutates the PhysicalIR or package bytes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from .model import AnalysisWarning

ANALYSIS_FORMATTING_VERSION = "0.1b-m1"

STYLES_PART_NAME = "word/styles.xml"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    ABSENT = "absent"
    UNRESOLVED = "unresolved"
    INVALID = "invalid"
    AMBIGUOUS = "ambiguous"


# --- Warning codes (closed set for Marco 1, per decision 0015) ---
W_MISSING_STYLE = "formatting_missing_style"
W_STYLE_CYCLE = "formatting_style_cycle"
W_INVALID_VALUE = "formatting_invalid_value"
W_DUPLICATE_PROPERTY = "formatting_duplicate_property"
W_WRONG_STYLE_TYPE = "formatting_wrong_style_type"
W_MULTIPLE_DEFAULT_STYLES = "formatting_multiple_default_styles"
W_DUPLICATE_STYLE_ID = "formatting_duplicate_style_id"
W_NUMBERING_PRESENT = "formatting_numbering_present"
W_STYLES_PART_UNREADABLE = "formatting_styles_part_unreadable"

# --- Unresolved reasons (closed set for Marco 1) ---
R_NUMBERING_INDENT = "numbering_indent_unsupported"
R_AUTOSPACING = "autospacing_unsupported"
R_UNSUPPORTED_UNIT = "unsupported_unit"
R_STYLE_CYCLE = "style_cycle"
R_STYLES_UNAVAILABLE = "styles_unavailable"


@dataclass(frozen=True)
class FormattingEvidence:
    source_kind: str  # "direct" | "style" | "doc_defaults"
    part: str
    structural_path: str
    style_id: str | None
    property_name: str
    raw_value: str | None


@dataclass(frozen=True)
class LevelEvidence:
    level: str  # "direct" | "character_style" | "paragraph_style" | "doc_defaults"
    declared: bool
    detail: str  # "declared" | "not_declared" | "invalid" | "duplicate_conflict" | ...
    evidence: FormattingEvidence | None


@dataclass(frozen=True)
class ResolvedValue:
    status: ResolutionStatus
    value: Any  # None unless status == RESOLVED
    winning_evidence: FormattingEvidence | None
    evidence_chain: tuple[LevelEvidence, ...]
    reason: str | None


@dataclass(frozen=True)
class Length:
    value: Decimal
    unit: str  # "pt"
    raw_value: str
    raw_unit: str  # "half_point" | "twip"


@dataclass(frozen=True)
class ThemeRef:
    theme_slot: str


@dataclass(frozen=True)
class LineSpacing:
    rule: str
    value: Decimal | None
    unit: str | None  # "multiple" | "pt"
    raw_line: str | None
    raw_rule: str | None


@dataclass(frozen=True)
class SpacingSpec:
    before: ResolvedValue
    after: ResolvedValue
    before_lines: ResolvedValue
    after_lines: ResolvedValue
    line: ResolvedValue  # value is LineSpacing when resolved


@dataclass(frozen=True)
class IndentSpec:
    left: ResolvedValue
    right: ResolvedValue
    start: ResolvedValue
    end: ResolvedValue
    first_line: ResolvedValue
    hanging: ResolvedValue


@dataclass(frozen=True)
class FontSpec:
    ascii: ResolvedValue
    h_ansi: ResolvedValue
    east_asia: ResolvedValue
    cs: ResolvedValue
    ascii_theme: ResolvedValue
    h_ansi_theme: ResolvedValue
    east_asia_theme: ResolvedValue
    cs_theme: ResolvedValue


@dataclass(frozen=True)
class LanguageSpec:
    val: ResolvedValue
    east_asia: ResolvedValue
    bidi: ResolvedValue


@dataclass(frozen=True)
class RawProperty:
    property_name: str
    raw_attrs: tuple[tuple[str, str | None], ...]
    canonical_xml: str
    structural_path: str


@dataclass(frozen=True)
class RawPropertyBag:
    source_path: str
    source_hash: str | None
    entries: tuple[RawProperty, ...]


@dataclass(frozen=True)
class StyleEntry:
    style_id: str
    style_type: str
    is_default: bool
    custom_style: bool
    based_on_id: str | None
    link_id: str | None
    name: str | None
    ppr_bag: RawPropertyBag | None
    rpr_bag: RawPropertyBag | None
    structural_path: str
    physical_hash: str


@dataclass(frozen=True)
class DocDefaults:
    rpr_bag: RawPropertyBag | None
    ppr_bag: RawPropertyBag | None


@dataclass(frozen=True)
class StyleCatalog:
    part_name: str
    part_sha256: str | None
    part_status: str  # "ok" | "missing" | "unreadable"
    doc_defaults: DocDefaults | None
    styles: tuple[StyleEntry, ...]
    catalog_warnings: tuple[AnalysisWarning, ...]


@dataclass(frozen=True)
class ResolvedRunFormatting:
    run_path: str
    run_hash: str
    font_size: ResolvedValue
    font_spec: FontSpec
    language: LanguageSpec
    underline: ResolvedValue
    vert_align: ResolvedValue
    analysis_warnings: tuple[AnalysisWarning, ...]


@dataclass(frozen=True)
class ResolvedParagraphFormatting:
    paragraph_path: str
    paragraph_hash: str
    paragraph_style_id: ResolvedValue
    alignment: ResolvedValue
    spacing: SpacingSpec
    indents: IndentSpec
    analysis_warnings: tuple[AnalysisWarning, ...]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in sorted(value.items())}
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    return value


def _serialize(obj: Any) -> bytes:
    return json.dumps(
        _jsonable(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def serialize_style_catalog(catalog: StyleCatalog) -> bytes:
    return _serialize(catalog)


def serialize_resolved_paragraph(fmt: ResolvedParagraphFormatting) -> bytes:
    return _serialize(fmt)


def serialize_resolved_run(fmt: ResolvedRunFormatting) -> bytes:
    return _serialize(fmt)
