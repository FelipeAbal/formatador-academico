"""Read-only Processing Report v0.1 builder (decision 0034)."""
from __future__ import annotations

from collections import OrderedDict

from ..classification.model import ClassificationStatus
from ..decision.model import Actionability
from ..operation_plan import decision_ref as canonical_decision_ref
from ..processing_session.model import ProcessingSessionResult
from ..transform_log import transform_ref
from .model import (
    PROCESSING_REPORT_VERSION,
    AppliedChangeItem,
    ClassificationItem,
    ProcessingReport,
    ProcessingReportContractError,
    ProcessingReportIntegrityError,
    ProcessingReportSummary,
    ReviewItem,
    StoryCoverage,
    UnappliedChangeItem,
)


def _build_story_coverage(session_result: ProcessingSessionResult) -> tuple[StoryCoverage, ...]:
    buckets: OrderedDict[str, dict[str, int]] = OrderedDict()
    for result in session_result.final_classifications:
        bucket = buckets.setdefault(
            result.story_id,
            {
                "total": 0,
                "classified": 0,
                "abstained": 0,
                "not_applicable": 0,
                "warnings": 0,
            },
        )
        bucket["total"] += 1
        if result.status is ClassificationStatus.CLASSIFIED:
            bucket["classified"] += 1
        elif result.status is ClassificationStatus.ABSTAINED:
            bucket["abstained"] += 1
        elif result.status is ClassificationStatus.NOT_APPLICABLE:
            bucket["not_applicable"] += 1
        else:  # defensive; frozen enum should make this impossible
            raise ProcessingReportIntegrityError("unexpected classification status")
        bucket["warnings"] += len(result.classification_warnings)

    return tuple(
        StoryCoverage(
            story_id=story_id,
            total_count=counts["total"],
            classified_count=counts["classified"],
            abstained_count=counts["abstained"],
            not_applicable_count=counts["not_applicable"],
            warning_count=counts["warnings"],
        )
        for story_id, counts in buckets.items()
    )


def build_processing_report(session_result: ProcessingSessionResult) -> ProcessingReport:
    if not isinstance(session_result, ProcessingSessionResult):
        raise ProcessingReportContractError("session_result must be ProcessingSessionResult")

    final_by_ref = {}
    for decision in session_result.final_decisions:
        ref = canonical_decision_ref(decision)
        if ref in final_by_ref:
            raise ProcessingReportIntegrityError("duplicate canonical final Decision ref")
        final_by_ref[ref] = decision

    applied = tuple(
        AppliedChangeItem(
            transform_ref=transform_ref(record),
            decision_ref=record.decision_ref,
            operation_ref=record.operation_ref,
            profile_ref=record.profile_ref,
            rule_ref=record.rule_ref,
            target=record.target,
            observed_before=record.precondition_observed,
            desired_applied=record.desired_value,
            input_package_sha256=record.input_package_sha256,
            output_package_sha256=record.output_package_sha256,
            changed_part=record.changed_part,
        )
        for record in session_result.transforms
    )

    unapplied_items = []
    for finding in session_result.findings:
        decision = final_by_ref.get(finding.decision_ref)
        if decision is None:
            raise ProcessingReportIntegrityError("finding has no final Decision")
        if decision.actionability is not Actionability.DETERMINISTIC_CHANGE:
            raise ProcessingReportIntegrityError("finding Decision is not deterministic_change")
        dt = decision.target
        ft = finding.target
        if not (
            dt.target_type == ft.target_type
            and dt.structural_path == ft.structural_path
            and dt.physical_hash == ft.physical_hash
            and dt.target_class == ft.target_class
            and dt.aspect_id == ft.aspect_id
            and dt.property_slot == ft.property_slot
        ):
            raise ProcessingReportIntegrityError("finding target does not match final Decision")
        unapplied_items.append(
            UnappliedChangeItem(
                finding_kind=finding.kind,
                decision_ref=finding.decision_ref,
                operation_ref=finding.operation_ref,
                profile_ref=decision.profile_ref,
                rule_ref=decision.rule_ref,
                target=finding.target,
                reason=finding.reason,
                compliance=decision.compliance,
                actionability=decision.actionability,
                analysis_status=decision.analysis_status,
                observed=decision.observed,
                desired_value=decision.desired_value,
                decision_reason=decision.reason,
            )
        )
    unapplied = tuple(unapplied_items)

    review = tuple(
        ReviewItem(
            decision_ref=canonical_decision_ref(decision),
            profile_ref=decision.profile_ref,
            rule_ref=decision.rule_ref,
            target=__import__(
                "formatador_academico.operation_plan.model",
                fromlist=["OperationTarget"],
            ).OperationTarget(
                target_type=decision.target.target_type,
                structural_path=decision.target.structural_path,
                physical_hash=decision.target.physical_hash,
                target_class=decision.target.target_class,
                aspect_id=decision.target.aspect_id,
                property_slot=decision.target.property_slot,
            ),
            compliance=decision.compliance,
            actionability=decision.actionability,
            reason=decision.reason,
            analysis_status=decision.analysis_status,
            observed=decision.observed,
            evidence_ref=decision.evidence_ref,
            decision_warnings=decision.decision_warnings,
        )
        for decision in session_result.final_decisions
        if decision.actionability in {Actionability.REVIEW, Actionability.HUMAN_CHOICE}
    )

    classification = tuple(
        ClassificationItem(
            classification_status=result.status,
            target_type=result.target_type,
            structural_path=result.structural_path,
            physical_hash=result.physical_hash,
            story_id=result.story_id,
            target_class=result.target_class.value if result.target_class is not None else None,
            reasons=result.reasons,
            basis=result.basis,
            provenance=result.provenance,
            metadata=result.metadata,
            classification_warnings=result.classification_warnings,
        )
        for result in session_result.final_classifications
        if result.status is ClassificationStatus.ABSTAINED or result.classification_warnings
    )

    classified_count = sum(
        1 for result in session_result.final_classifications
        if result.status is ClassificationStatus.CLASSIFIED
    )
    abstained_count = sum(
        1 for result in session_result.final_classifications
        if result.status is ClassificationStatus.ABSTAINED
    )
    not_applicable_count = sum(
        1 for result in session_result.final_classifications
        if result.status is ClassificationStatus.NOT_APPLICABLE
    )
    warning_count = sum(
        len(result.classification_warnings)
        for result in session_result.final_classifications
    )
    story_coverage = _build_story_coverage(session_result)

    summary = ProcessingReportSummary(
        session_status=session_result.status,
        applied_change_count=len(applied),
        unapplied_change_count=len(unapplied),
        review_item_count=len(review),
        classification_item_count=len(classification),
        final_decision_count=len(session_result.final_decisions),
        final_classification_count=len(session_result.final_classifications),
        classified_count=classified_count,
        abstained_count=abstained_count,
        not_applicable_count=not_applicable_count,
        classification_warning_count=warning_count,
        story_coverage=story_coverage,
        input_package_sha256=session_result.input_package_sha256,
        output_package_sha256=session_result.output_package_sha256,
    )

    return ProcessingReport(
        processing_report_version=PROCESSING_REPORT_VERSION,
        processing_session_version=session_result.processing_session_version,
        profile_ref=session_result.profile_ref,
        summary=summary,
        applied_changes=applied,
        unapplied_changes=unapplied,
        review_items=review,
        classification_items=classification,
    )
