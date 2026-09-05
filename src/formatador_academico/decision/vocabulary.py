"""Decision Vocabulary v0.1 registry and Analysis boundary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .model import DecisionKey

DECISION_VOCABULARY_VERSION = "0.1"

@dataclass(frozen=True)
class VocabularyEntry:
    key: DecisionKey
    analysis_source: str
    supported_in_slice: bool

_ENTRIES = (
    VocabularyEntry(DecisionKey("run", "P1", "bold"), "ResolvedRunFormatting.bold", True),
    VocabularyEntry(DecisionKey("run", "P1", "italic"), "ResolvedRunFormatting.italic", False),
    VocabularyEntry(DecisionKey("run", "P2", "font_size"), "ResolvedRunFormatting.font_size", True),
    VocabularyEntry(DecisionKey("paragraph", "P3", "spacing.line"), "ResolvedParagraphFormatting.spacing.line", True),
    VocabularyEntry(DecisionKey("paragraph", "P4", "alignment"), "ResolvedParagraphFormatting.alignment", True),
)
_BY_KEY = {entry.key: entry for entry in _ENTRIES}
SUPPORTED_KEYS = tuple(entry.key for entry in _ENTRIES if entry.supported_in_slice)

def vocabulary_entry(key: DecisionKey) -> VocabularyEntry:
    try:
        return _BY_KEY[key]
    except KeyError as exc:
        raise ValueError(f"DecisionKey not in vocabulary v{DECISION_VOCABULARY_VERSION}: {key}") from exc

def require_supported_key(key: DecisionKey) -> VocabularyEntry:
    entry = vocabulary_entry(key)
    if not entry.supported_in_slice:
        raise ValueError(f"DecisionKey is frozen but outside current vertical slice: {key}")
    return entry

def _boundary_getattr(analysis: Any, source: str, key: DecisionKey) -> Any:
    obj = analysis
    for attr in source.split(".")[1:]:
        try:
            obj = getattr(obj, attr)
        except AttributeError as exc:
            raise TypeError(
                f"analysis object of type {type(analysis).__name__} does not satisfy "
                f"the vocabulary boundary {source} for {key}"
            ) from exc
    return obj

def extract_resolved_value(key: DecisionKey, analysis: Any):
    entry = require_supported_key(key)
    if entry.analysis_source == "ResolvedRunFormatting.bold":
        return _boundary_getattr(analysis, entry.analysis_source, key)
    if entry.analysis_source == "ResolvedRunFormatting.font_size":
        return _boundary_getattr(analysis, entry.analysis_source, key)
    if entry.analysis_source == "ResolvedParagraphFormatting.spacing.line":
        return _boundary_getattr(analysis, entry.analysis_source, key)
    if entry.analysis_source == "ResolvedParagraphFormatting.alignment":
        return _boundary_getattr(analysis, entry.analysis_source, key)
    raise AssertionError("unreachable vocabulary mapping")
