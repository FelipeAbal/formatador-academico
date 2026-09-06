"""OperationPlan v0.1 — first vertical slice (Decision -> OperationPlan).

Contract: docs/decisions/0024-operation-plan-v01-contract.md.

The planner is a pure, deterministic transformation over frozen Decisions.
It never re-decides compliance, never consults profile/rule to pick values,
never opens DOCX/XML, never calls parser/Analysis/SafetyGate, never uses
LLM/random/clock/locale.
"""

from .model import (
    OPERATION_PLAN_VERSION,
    OPERATION_VOCABULARY_VERSION,
    PLANNED_STORY_PART,
    LengthValue,
    OperationKind,
    OperationPlan,
    OperationTarget,
    PlannedOperation,
    PlanningResult,
    PlanningStatus,
    SourceDocumentRef,
    UpstreamVersions,
)
from .planner import (
    OperationPlanAggregationError,
    OperationPlanContractError,
    OperationPlanError,
    build_operation_plan,
    decision_ref,
    plan_decision,
    source_decisions_hash,
)
from .serialization import (
    operation_plan_ref,
    operation_ref,
    serialize_operation_plan,
    serialize_planned_operation,
    serialize_planning_result,
    serialize_planning_results,
)
from .boundary import source_document_ref_from_physical_ir

__all__ = [
    "OPERATION_PLAN_VERSION",
    "OPERATION_VOCABULARY_VERSION",
    "PLANNED_STORY_PART",
    "LengthValue",
    "OperationKind",
    "OperationPlan",
    "OperationPlanAggregationError",
    "OperationPlanContractError",
    "OperationPlanError",
    "OperationTarget",
    "PlannedOperation",
    "PlanningResult",
    "PlanningStatus",
    "SourceDocumentRef",
    "UpstreamVersions",
    "build_operation_plan",
    "decision_ref",
    "operation_plan_ref",
    "operation_ref",
    "plan_decision",
    "serialize_operation_plan",
    "serialize_planned_operation",
    "serialize_planning_result",
    "serialize_planning_results",
    "source_decisions_hash",
    "source_document_ref_from_physical_ir",
]
