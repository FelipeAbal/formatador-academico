"""Classification Layer v0.1 — document classifier (first vertical slice).

Executable slice: `body`, `heading`, abstention. `long_quote` and
`reference` stay in the vocabulary but are never produced here.

Public API (decision 0022):

    classify_document(physical_ir, style_catalog) -> tuple[ClassificationResult, ...]
    project_run_classification(run, paragraph_result) -> ClassificationResult

`classify_document` derives Normalized Text and Formatting Analysis per
paragraph internally, straight from the PhysicalIR + StyleCatalog it was
given. This guarantees input binding by construction: a paragraph whose
Analysis binding is broken raises a contract error (briefing item 36) instead
of being silently misread as `insufficient_evidence`.

Reason priority (frozen in 0022):
    unsupported_story > unsupported_target > parent_not_classified
    > empty_content > unsupported_context > conflicting_evidence
    > insufficient_evidence > positive reasons.

This module must never import the normative profile side of the Decision
Layer (no FormattingRule / ProfileRef / ValidatedProfile) and never touch
raw OOXML/lxml.
"""

from __future__ import annotations

from typing import Any, Iterator

from ..analysis.formatting import resolve_paragraph_formatting
from ..analysis.formatting_model import (
    W_MISSING_STYLE,
    W_NUMBERING_PRESENT,
    ResolutionStatus,
    StyleCatalog,
)
from ..analysis.normalized_text import normalize_paragraph
from ..analysis.style_catalog import default_styles
from .identity import IdentityOutcome, IdentityVia, resolve_style_identity
from .model import (
    CLASSIFICATION_VERSION,
    CLASSIFICATION_VOCABULARY_VERSION,
    ClassificationEvidence,
    ClassificationReason,
    ClassificationResult,
    ClassificationStatus,
    ClassificationBasis,
    ClassificationProvenance,
    ClassificationWarning,
    EvidencePolarity,
    EvidenceSourceKind,
    EvidenceStrength,
    ParentAnchor,
    TargetClass,
)

W_STYLE_REF_DANGLING = "classification_style_ref_dangling"

_BODY_STORY_TYPE = "body"
_CONTAINER_SOURCE_TYPES = frozenset(
    {"table", "table_row", "table_cell", "block_container"}
)


def _iter_paragraphs(
    blocks: list[dict[str, Any]], in_container: str | None
) -> Iterator[tuple[dict[str, Any], str | None]]:
    """Yield (paragraph, container_kind) in document order.

    container_kind is the nearest enclosing container source_type (table,
    table_row, table_cell, block_container or a depth-limited wrapper), or
    None for top-level body blocks. Run children of paragraphs are never
    descended into.
    """
    for block in blocks:
        if not isinstance(block, dict):
            continue
        source_type = block.get("source_type")
        if source_type == "paragraph":
            yield block, in_container
            continue
        child_container = in_container
        if source_type in _CONTAINER_SOURCE_TYPES or block.get("depth_limited"):
            child_container = source_type or "depth_limited"
        children = block.get("children")
        if isinstance(children, list):
            yield from _iter_paragraphs(children, child_container)


def _result(
    *,
    target_type: str,
    structural_path: str,
    physical_hash: str,
    story_id: str,
    status: ClassificationStatus,
    target_class: TargetClass | None = None,
    metadata: tuple[tuple[str, Any], ...] = (),
    basis: ClassificationBasis | None = None,
    reasons: tuple[ClassificationReason, ...],
    evidence: tuple[ClassificationEvidence, ...] = (),
    provenance: ClassificationProvenance = ClassificationProvenance.DIRECT,
    parent_anchor: ParentAnchor | None = None,
    warnings: tuple[ClassificationWarning, ...] = (),
) -> ClassificationResult:
    return ClassificationResult(
        classification_version=CLASSIFICATION_VERSION,
        classification_vocabulary_version=CLASSIFICATION_VOCABULARY_VERSION,
        target_type=target_type,
        structural_path=structural_path,
        physical_hash=physical_hash,
        story_id=story_id,
        status=status,
        target_class=target_class,
        metadata=metadata,
        basis=basis,
        reasons=reasons,
        evidence=evidence,
        provenance=provenance,
        parent_anchor=parent_anchor,
        classification_warnings=warnings,
    )


def _classify_paragraph(
    paragraph: dict[str, Any],
    story_id: str,
    story_type: str,
    part: str,
    container: str | None,
    catalog: StyleCatalog,
) -> ClassificationResult:
    if paragraph.get("source_type") != "paragraph":
        raise ValueError("classify_document requires PhysicalIR paragraph records")
    if not paragraph.get("structural_path") or not paragraph.get("physical_hash"):
        raise ValueError(
            "paragraph lacks provenance required by Classification; a broken "
            "Analysis binding is a contract/input error, not insufficient evidence"
        )
    path = paragraph["structural_path"]
    p_hash = paragraph["physical_hash"]

    def make(**kwargs: Any) -> ClassificationResult:
        return _result(
            target_type="paragraph",
            structural_path=path,
            physical_hash=p_hash,
            story_id=story_id,
            **kwargs,
        )

    # Priority 1: unsupported story.
    if story_type != _BODY_STORY_TYPE:
        return make(
            status=ClassificationStatus.NOT_APPLICABLE,
            reasons=(ClassificationReason.UNSUPPORTED_STORY,),
        )

    # Priority 3: empty content (before unsupported_context, per 0022).
    normalized = normalize_paragraph(paragraph, story_id, part)
    if not normalized.default_text.strip():
        return make(
            status=ClassificationStatus.ABSTAINED,
            reasons=(ClassificationReason.EMPTY_CONTENT,),
            evidence=(
                ClassificationEvidence(
                    source_kind=EvidenceSourceKind.NORMALIZED_TEXT,
                    source_ref=normalized.paragraph_path,
                    feature="default_text",
                    observed_value="",
                    polarity=EvidencePolarity.SUPPORTS,
                    strength=EvidenceStrength.STRUCTURAL,
                ),
            ),
        )

    paragraph_formatting = resolve_paragraph_formatting(paragraph, catalog, part)

    # Priority 4: unsupported context — containment, then numbering.
    if container is not None:
        return make(
            status=ClassificationStatus.ABSTAINED,
            reasons=(ClassificationReason.UNSUPPORTED_CONTEXT,),
            evidence=(
                ClassificationEvidence(
                    source_kind=EvidenceSourceKind.PHYSICAL_STRUCTURE,
                    source_ref=path,
                    feature="containment",
                    observed_value=container,
                    polarity=EvidencePolarity.SUPPORTS,
                    strength=EvidenceStrength.STRUCTURAL,
                ),
            ),
        )
    if any(w.code == W_NUMBERING_PRESENT for w in paragraph_formatting.analysis_warnings):
        return make(
            status=ClassificationStatus.ABSTAINED,
            reasons=(ClassificationReason.UNSUPPORTED_CONTEXT,),
            evidence=(
                ClassificationEvidence(
                    source_kind=EvidenceSourceKind.FORMATTING_ANALYSIS,
                    source_ref=path,
                    feature="numbering_presence",
                    observed_value=W_NUMBERING_PRESENT,
                    polarity=EvidencePolarity.SUPPORTS,
                    strength=EvidenceStrength.STRUCTURAL,
                ),
            ),
        )

    # Positive identity: direct w:pStyle, else the applicable default
    # paragraph style (decision 0016: the LAST default entry applies).
    style_ref = paragraph_formatting.paragraph_style_id
    identity_evidence: list[ClassificationEvidence] = []
    style_id: str | None = None
    if style_ref.status is ResolutionStatus.RESOLVED:
        style_id = style_ref.value
        identity_evidence.append(
            ClassificationEvidence(
                source_kind=EvidenceSourceKind.FORMATTING_ANALYSIS,
                source_ref=path,
                feature="paragraph_style_id",
                observed_value=style_id,
                polarity=EvidencePolarity.SUPPORTS,
                strength=EvidenceStrength.EXPLICIT,
            )
        )
    elif style_ref.status is ResolutionStatus.ABSENT:
        defaults = default_styles(catalog, "paragraph")
        default_entry = defaults[-1] if defaults else None
        if default_entry is not None and default_entry.style_id is not None:
            style_id = default_entry.style_id
            identity_evidence.append(
                ClassificationEvidence(
                    source_kind=EvidenceSourceKind.STYLE_CATALOG,
                    source_ref=default_entry.structural_path,
                    feature="default_paragraph_style",
                    observed_value=style_id,
                    polarity=EvidencePolarity.SUPPORTS,
                    strength=EvidenceStrength.EXPLICIT,
                )
            )
    # UNRESOLVED / INVALID / AMBIGUOUS or no usable default: no identity.
    if style_id is None:
        return make(
            status=ClassificationStatus.ABSTAINED,
            reasons=(ClassificationReason.INSUFFICIENT_EVIDENCE,),
        )

    resolution = resolve_style_identity(catalog, style_id)
    if resolution.outcome is IdentityOutcome.IDENTIFIED:
        if resolution.via is IdentityVia.BASED_ON_CHAIN:
            identity_evidence.append(
                ClassificationEvidence(
                    source_kind=EvidenceSourceKind.STYLE_CATALOG,
                    source_ref=path,
                    feature="based_on_chain",
                    observed_value=">".join(resolution.chain),
                    polarity=EvidencePolarity.SUPPORTS,
                    strength=EvidenceStrength.EXPLICIT,
                )
            )
        metadata: tuple[tuple[str, Any], ...] = ()
        if resolution.target_class is TargetClass.HEADING:
            metadata = (("level", resolution.level),)
        return make(
            status=ClassificationStatus.CLASSIFIED,
            target_class=resolution.target_class,
            metadata=metadata,
            basis=ClassificationBasis.EXPLICIT,
            reasons=(ClassificationReason.EXPLICIT_STYLE_SIGNAL,),
            evidence=tuple(identity_evidence),
        )

    # Dangling style reference is a contract anomaly worth a warning — but the
    # Analysis layer already reports it as formatting_missing_style; never
    # duplicate that signal (briefing item 37).
    warnings: tuple[ClassificationWarning, ...] = ()
    if resolution.outcome is IdentityOutcome.BROKEN_CHAIN and not any(
        w.code in (W_MISSING_STYLE,) for w in paragraph_formatting.analysis_warnings
    ):
        warnings = (
            ClassificationWarning(
                code=W_STYLE_REF_DANGLING,
                message=(
                    f"Style identity chain {list(resolution.chain)} did not resolve "
                    "to a catalog entry; classification abstained."
                ),
                structural_path=path,
            ),
        )
    identity_evidence.append(
        ClassificationEvidence(
            source_kind=EvidenceSourceKind.STYLE_CATALOG,
            source_ref=path,
            feature="style_identity_chain",
            observed_value=">".join(resolution.chain),
            polarity=EvidencePolarity.SUPPORTS,
            strength=EvidenceStrength.EXPLICIT,
        )
    )
    return make(
        status=ClassificationStatus.ABSTAINED,
        reasons=(ClassificationReason.INSUFFICIENT_EVIDENCE,),
        evidence=tuple(identity_evidence),
        warnings=warnings,
    )


def classify_document(
    physical_ir: dict[str, Any], style_catalog: StyleCatalog
) -> tuple[ClassificationResult, ...]:
    """Classify every paragraph of every story, in document order.

    Secondary stories are not classified: each of their paragraphs yields
    not_applicable/unsupported_story. One abstained or not-applicable target
    never takes down the others; contract violations (broken Analysis
    binding) raise, because they are programming/input bugs, not evidence
    problems.
    """
    if not isinstance(physical_ir, dict) or physical_ir.get("status") != "ok":
        raise ValueError("classify_document requires a PhysicalIR with status == ok")
    if not isinstance(style_catalog, StyleCatalog):
        raise TypeError("style_catalog must be a StyleCatalog")
    results: list[ClassificationResult] = []
    for story in physical_ir["stories"]:
        story_id = story["story_id"]
        story_type = story["story_type"]
        part = story["part"]
        for paragraph, container in _iter_paragraphs(story.get("blocks") or [], None):
            results.append(
                _classify_paragraph(
                    paragraph, story_id, story_type, part, container, style_catalog
                )
            )
    return tuple(results)


def project_run_classification(
    run: dict[str, Any], paragraph_result: ClassificationResult
) -> ClassificationResult:
    """Project a paragraph's class onto one of its runs (never a new
    classification).

    A run of a non-classified paragraph receives
    not_applicable/parent_not_classified — never an invented class.
    """
    if not isinstance(run, dict) or run.get("source_type") != "run_raw":
        raise ValueError("project_run_classification requires a PhysicalIR run_raw record")
    if not run.get("structural_path") or not run.get("physical_hash"):
        raise ValueError("run lacks provenance required for classification projection")
    if paragraph_result.target_type != "paragraph":
        raise ValueError("paragraph_result must classify a paragraph target")

    run_path = run["structural_path"]
    run_hash = run["physical_hash"]

    def make(**kwargs: Any) -> ClassificationResult:
        return _result(
            target_type="run",
            structural_path=run_path,
            physical_hash=run_hash,
            story_id=paragraph_result.story_id,
            **kwargs,
        )

    if paragraph_result.status is not ClassificationStatus.CLASSIFIED:
        return make(
            status=ClassificationStatus.NOT_APPLICABLE,
            reasons=(ClassificationReason.PARENT_NOT_CLASSIFIED,),
        )
    assert paragraph_result.target_class is not None  # model invariant
    return make(
        status=ClassificationStatus.CLASSIFIED,
        target_class=paragraph_result.target_class,
        metadata=paragraph_result.metadata,
        basis=paragraph_result.basis,
        reasons=(ClassificationReason.INHERITED_FROM_PARAGRAPH,),
        evidence=(
            ClassificationEvidence(
                source_kind=EvidenceSourceKind.SEQUENCE_CONTEXT,
                source_ref=paragraph_result.structural_path,
                feature="parent_paragraph_classification",
                observed_value=paragraph_result.target_class.value,
                polarity=EvidencePolarity.SUPPORTS,
                strength=EvidenceStrength.STRUCTURAL,
            ),
        ),
        provenance=ClassificationProvenance.INHERITED_FROM_PARAGRAPH,
        parent_anchor=ParentAnchor(
            structural_path=paragraph_result.structural_path,
            physical_hash=paragraph_result.physical_hash,
        ),
    )
