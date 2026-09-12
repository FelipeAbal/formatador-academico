"""Classification Layer v0.1 — public immutable models.

Contract: docs/decisions/0022-classification-layer-v01-contract.md.

The layer transforms documental facts (PhysicalIR + Normalized Text v0.1a +
Formatting Analysis v0.1b + StyleCatalog) into academic block classification.
It never decides conformance, never reads a normative profile, never parses
raw OOXML, and never mutates its inputs.

precision > coverage. Abstention is a safe, expected result. `body` is never
a residual fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

CLASSIFICATION_VERSION = "0.1"
CLASSIFICATION_VOCABULARY_VERSION = "0.1"


class TargetClass(str, Enum):
    """Closed v0.1 vocabulary. `unknown` is NOT a class.

    LONG_QUOTE and REFERENCE belong to the vocabulary but are outside the
    first executable slice: the slice never produces them.
    """

    BODY = "body"
    HEADING = "heading"
    LONG_QUOTE = "long_quote"
    REFERENCE = "reference"


class ClassificationStatus(str, Enum):
    CLASSIFIED = "classified"
    ABSTAINED = "abstained"
    NOT_APPLICABLE = "not_applicable"


class ClassificationBasis(str, Enum):
    EXPLICIT = "explicit"
    STRUCTURAL = "structural"
    HEURISTIC = "heuristic"


class ClassificationProvenance(str, Enum):
    DIRECT = "direct"
    INHERITED_FROM_PARAGRAPH = "inherited_from_paragraph"


class EvidenceSourceKind(str, Enum):
    PHYSICAL_STRUCTURE = "physical_structure"
    NORMALIZED_TEXT = "normalized_text"
    FORMATTING_ANALYSIS = "formatting_analysis"
    STYLE_CATALOG = "style_catalog"
    SEQUENCE_CONTEXT = "sequence_context"


class EvidencePolarity(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


class EvidenceStrength(str, Enum):
    EXPLICIT = "explicit"
    STRUCTURAL = "structural"
    WEAK = "weak"


class ClassificationReason(str, Enum):
    # classification
    EXPLICIT_STYLE_SIGNAL = "explicit_style_signal"
    STRUCTURAL_CONTEXT_SIGNAL = "structural_context_signal"
    INHERITED_FROM_PARAGRAPH = "inherited_from_paragraph"
    # abstention
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    EMPTY_CONTENT = "empty_content"
    UNSUPPORTED_CONTEXT = "unsupported_context"
    # not applicable
    UNSUPPORTED_STORY = "unsupported_story"
    UNSUPPORTED_TARGET = "unsupported_target"
    PARENT_NOT_CLASSIFIED = "parent_not_classified"


_CLASSIFIED_REASONS = frozenset(
    {
        ClassificationReason.EXPLICIT_STYLE_SIGNAL,
        ClassificationReason.STRUCTURAL_CONTEXT_SIGNAL,
        ClassificationReason.INHERITED_FROM_PARAGRAPH,
    }
)
_ABSTAINED_REASONS = frozenset(
    {
        ClassificationReason.INSUFFICIENT_EVIDENCE,
        ClassificationReason.CONFLICTING_EVIDENCE,
        ClassificationReason.EMPTY_CONTENT,
        ClassificationReason.UNSUPPORTED_CONTEXT,
    }
)
_NOT_APPLICABLE_REASONS = frozenset(
    {
        ClassificationReason.UNSUPPORTED_STORY,
        ClassificationReason.UNSUPPORTED_TARGET,
        ClassificationReason.PARENT_NOT_CLASSIFIED,
    }
)

_METADATA_SCALAR_TYPES = (str, int, bool, type(None))


@dataclass(frozen=True)
class ClassificationEvidence:
    """An observed fact, never a conclusion. Closed enums where applicable."""

    source_kind: EvidenceSourceKind
    source_ref: str
    feature: str
    observed_value: str
    polarity: EvidencePolarity
    strength: EvidenceStrength

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, EvidenceSourceKind):
            raise TypeError("source_kind must be EvidenceSourceKind")
        if not isinstance(self.polarity, EvidencePolarity):
            raise TypeError("polarity must be EvidencePolarity")
        if not isinstance(self.strength, EvidenceStrength):
            raise TypeError("strength must be EvidenceStrength")


@dataclass(frozen=True)
class ParentAnchor:
    structural_path: str
    physical_hash: str


@dataclass(frozen=True)
class ClassificationWarning:
    """Contract/execution anomaly. Normal abstention is NEVER a warning."""

    code: str
    message: str
    structural_path: str


@dataclass(frozen=True)
class ClassificationResult:
    classification_version: str
    classification_vocabulary_version: str
    target_type: str
    structural_path: str
    physical_hash: str
    story_id: str
    status: ClassificationStatus
    target_class: TargetClass | None
    metadata: tuple[tuple[str, str | int | bool | None], ...]
    basis: ClassificationBasis | None
    reasons: tuple[ClassificationReason, ...]
    evidence: tuple[ClassificationEvidence, ...]
    provenance: ClassificationProvenance
    parent_anchor: ParentAnchor | None
    classification_warnings: tuple[ClassificationWarning, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ClassificationStatus):
            raise TypeError("status must be ClassificationStatus")
        if self.target_class is not None and not isinstance(self.target_class, TargetClass):
            raise TypeError("target_class must be TargetClass or None")
        if not isinstance(self.metadata, tuple):
            raise TypeError("metadata must be an immutable tuple of pairs")
        keys = []
        for pair in self.metadata:
            if not (isinstance(pair, tuple) and len(pair) == 2 and isinstance(pair[0], str)):
                raise TypeError("metadata entries must be (str, scalar) tuples")
            if not isinstance(pair[1], _METADATA_SCALAR_TYPES):
                raise TypeError("metadata values must be scalars (str/int/bool/None)")
            keys.append(pair[0])
        if keys != sorted(keys) or len(set(keys)) != len(keys):
            raise ValueError("metadata keys must be unique and sorted")
        if not isinstance(self.reasons, tuple) or not self.reasons:
            raise ValueError("reasons must be a non-empty tuple")
        for reason in self.reasons:
            if not isinstance(reason, ClassificationReason):
                raise TypeError("reasons must be ClassificationReason members")
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple")
        if not isinstance(self.provenance, ClassificationProvenance):
            raise TypeError("provenance must be ClassificationProvenance")

        classified = self.status is ClassificationStatus.CLASSIFIED
        # Hard invariant: status == classified IFF target_class is not None.
        if classified != (self.target_class is not None):
            raise ValueError("status == classified iff target_class is not None")
        if classified:
            if not self.evidence:
                raise ValueError("classified results require non-empty evidence")
            if self.basis is None:
                raise ValueError("classified results require a basis")
            if not set(self.reasons) <= _CLASSIFIED_REASONS:
                raise ValueError("classified results only accept classification reasons")
        else:
            if self.basis is not None:
                raise ValueError("non-classified results cannot carry a basis")
            allowed = (
                _ABSTAINED_REASONS
                if self.status is ClassificationStatus.ABSTAINED
                else _NOT_APPLICABLE_REASONS
            )
            if not set(self.reasons) <= allowed:
                raise ValueError(f"reasons incompatible with status {self.status.value}")
        if self.provenance is ClassificationProvenance.INHERITED_FROM_PARAGRAPH:
            if self.target_type != "run":
                raise ValueError("inherited_from_paragraph requires target_type == run")
            if self.parent_anchor is None:
                raise ValueError("inherited_from_paragraph requires parent_anchor")
        if self.provenance is ClassificationProvenance.DIRECT and self.parent_anchor is not None:
            raise ValueError("direct provenance cannot carry parent_anchor")


def eligible_for_automatic_use(result: ClassificationResult) -> bool:
    """Pure function; NOT a stored field (decision 0022).

    eligible iff status == classified AND basis in {explicit, structural}.
    `heuristic` never projects automatically in v0.1.
    """
    return result.status is ClassificationStatus.CLASSIFIED and result.basis in (
        ClassificationBasis.EXPLICIT,
        ClassificationBasis.STRUCTURAL,
    )
