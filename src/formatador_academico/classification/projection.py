"""Safe projection from ClassificationResult to the frozen
decision.TargetClassification model (decision 0021, unchanged).

Only results eligible for automatic use may project:
    status == classified AND basis in {explicit, structural}.
Anything else is an explicit error. Abstained / not_applicable / heuristic
results never reach the Decision Layer through this function.
"""

from __future__ import annotations

from ..decision.model import TargetClassification
from .model import (
    CLASSIFICATION_VERSION,
    ClassificationProvenance,
    ClassificationResult,
    eligible_for_automatic_use,
)

_PROJECTION_PROVENANCE = {
    ClassificationProvenance.DIRECT: "classification:direct",
    ClassificationProvenance.INHERITED_FROM_PARAGRAPH: (
        "classification:inherited_from_paragraph"
    ),
}


def project_target_classification(result: ClassificationResult) -> TargetClassification:
    if not isinstance(result, ClassificationResult):
        raise TypeError("project_target_classification requires a ClassificationResult")
    if not eligible_for_automatic_use(result):
        raise ValueError(
            "only results with status == classified and basis in "
            "{explicit, structural} may project to TargetClassification "
            f"(got status={result.status.value}, basis="
            f"{result.basis.value if result.basis is not None else None})"
        )
    assert result.target_class is not None  # model invariant
    return TargetClassification(
        target_type=result.target_type,
        structural_path=result.structural_path,
        physical_hash=result.physical_hash,
        target_class=result.target_class.value,
        classification_version=CLASSIFICATION_VERSION,
        provenance=_PROJECTION_PROVENANCE[result.provenance],
    )
