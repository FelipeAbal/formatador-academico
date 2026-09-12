from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class SegmentKind(str, Enum):
    TEXT = "TEXT"
    TAB = "TAB"
    LINE_BREAK = "LINE_BREAK"
    PAGE_BREAK = "PAGE_BREAK"
    COLUMN_BREAK = "COLUMN_BREAK"
    CARRIAGE_RETURN = "CARRIAGE_RETURN"
    NO_BREAK_HYPHEN = "NO_BREAK_HYPHEN"
    SOFT_HYPHEN = "SOFT_HYPHEN"
    SYMBOL = "SYMBOL"
    FIELD_CODE = "FIELD_CODE"
    DELETED_TEXT = "DELETED_TEXT"
    OPAQUE = "OPAQUE"


class TextRole(str, Enum):
    CONTENT = "CONTENT"
    DELETED = "DELETED"
    FIELD_INTERNAL = "FIELD_INTERNAL"
    STRUCTURAL = "STRUCTURAL"
    OPAQUE = "OPAQUE"


@dataclass(frozen=True)
class SourceAnchor:
    story_id: str
    part: str
    structural_path: str
    physical_hash: str
    fragment_type: str
    source_start: int
    source_end: int


@dataclass(frozen=True)
class AnalysisWarning:
    code: str
    message: str
    structural_path: str


@dataclass(frozen=True)
class NormalizedSegment:
    segment_kind: SegmentKind
    text_role: TextRole
    raw_text: str | None
    projected_text: str | None
    logical_start: int
    logical_end: int
    contributes_to_default_text: bool
    source: SourceAnchor
    metadata: tuple[tuple[str, str | None], ...] | None = None


@dataclass(frozen=True)
class NormalizedParagraph:
    paragraph_path: str
    paragraph_hash: str
    segments: tuple[NormalizedSegment, ...]
    default_text: str
    has_non_content: bool
    analysis_warnings: tuple[AnalysisWarning, ...]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in sorted(value.items())}
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    return value


def serialize_normalized_paragraph(paragraph: NormalizedParagraph) -> bytes:
    return json.dumps(
        _jsonable(paragraph), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def normalized_paragraph_to_json(paragraph: NormalizedParagraph) -> str:
    return serialize_normalized_paragraph(paragraph).decode("utf-8")
