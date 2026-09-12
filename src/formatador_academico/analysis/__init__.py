"""Analysis View v0.1a — Normalized Text View."""

from .model import (
    AnalysisWarning,
    NormalizedParagraph,
    NormalizedSegment,
    SegmentKind,
    SourceAnchor,
    TextRole,
    normalized_paragraph_to_json,
    serialize_normalized_paragraph,
)
from .normalized_text import normalize_paragraph

__all__ = [
    "AnalysisWarning",
    "NormalizedParagraph",
    "NormalizedSegment",
    "SegmentKind",
    "SourceAnchor",
    "TextRole",
    "normalize_paragraph",
    "normalized_paragraph_to_json",
    "serialize_normalized_paragraph",
]
