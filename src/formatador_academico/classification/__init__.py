"""Classification Layer v0.1 — first vertical slice (body / heading / abstain).

Contract: docs/decisions/0022-classification-layer-v01-contract.md.
"""

from .model import (
    CLASSIFICATION_VERSION,
    CLASSIFICATION_VOCABULARY_VERSION,
    ClassificationBasis,
    ClassificationEvidence,
    ClassificationProvenance,
    ClassificationReason,
    ClassificationResult,
    ClassificationStatus,
    ClassificationWarning,
    EvidencePolarity,
    EvidenceSourceKind,
    EvidenceStrength,
    ParentAnchor,
    TargetClass,
    eligible_for_automatic_use,
)
from .identity import (
    CLASSIFICATION_STYLE_IDENTITY_VERSION,
    IdentityOutcome,
    IdentityVia,
    StyleIdentityResolution,
    resolve_style_identity,
)
from .classifier import (
    W_STYLE_REF_DANGLING,
    classify_document,
    project_run_classification,
)
from .projection import project_target_classification
from .serialization import (
    classification_result_to_json,
    serialize_classification_result,
    serialize_classification_results,
)

__all__ = [
    "CLASSIFICATION_VERSION",
    "CLASSIFICATION_VOCABULARY_VERSION",
    "CLASSIFICATION_STYLE_IDENTITY_VERSION",
    "ClassificationBasis",
    "ClassificationEvidence",
    "ClassificationProvenance",
    "ClassificationReason",
    "ClassificationResult",
    "ClassificationStatus",
    "ClassificationWarning",
    "EvidencePolarity",
    "EvidenceSourceKind",
    "EvidenceStrength",
    "IdentityOutcome",
    "IdentityVia",
    "ParentAnchor",
    "StyleIdentityResolution",
    "TargetClass",
    "W_STYLE_REF_DANGLING",
    "classify_document",
    "classification_result_to_json",
    "eligible_for_automatic_use",
    "project_run_classification",
    "project_target_classification",
    "resolve_style_identity",
    "serialize_classification_result",
    "serialize_classification_results",
]
