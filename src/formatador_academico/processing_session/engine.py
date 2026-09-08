"""Processing Session v0.1 deterministic orchestration (decision 0032)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterator

from ..analysis.formatting import resolve_run_formatting
from ..analysis.formatting_model import ANALYSIS_FORMATTING_VERSION
from ..analysis.style_catalog import build_style_catalog
from ..classification import (
    CLASSIFICATION_VERSION,
    ClassificationResult,
    classify_document,
    eligible_for_automatic_use,
    project_run_classification,
    project_target_classification,
)
from ..decision import (
    DECISION_VERSION,
    DECISION_VOCABULARY_VERSION,
    Actionability,
    Decision,
    DecisionContext,
    DecisionKey,
    evaluate_target,
    extract_resolved_value,
)
from ..docx_parser import DocxParser
from ..operation_plan import (
    UpstreamVersions,
    build_operation_plan,
    decision_ref,
    source_document_ref_from_physical_ir,
)
from ..patcher import PatchReason, PatchStatus, apply_cleared_operation
from ..safety_gate import GateStatus, SafetyGateReport, evaluate_operation_plan
from ..transform_log import build_transform_record
from .model import (
    DEFAULT_MAX_APPLIED_OPERATIONS,
    PROCESSING_SESSION_VERSION,
    ProcessingProfile,
    ProcessingSessionContractError,
    ProcessingSessionIntegrityError,
    ProcessingSessionResult,
    ProcessingSessionStatus,
    SessionFinding,
    SessionFindingKind,
)


@dataclass(frozen=True)
class _ParagraphBinding:
    story_id: str
    part: str
    paragraph: dict[str, Any]


@dataclass(frozen=True)
class _EvaluationSnapshot:
    package_sha256: str
    physical_ir: dict[str, Any]
    style_catalog: Any
    classifications: tuple[ClassificationResult, ...]
    decisions: tuple[Decision, ...]
    plan: Any
    gate_report: SafetyGateReport


_IMPOSSIBLE_PATCH_REJECTIONS = frozenset(
    {PatchReason.SNAPSHOT_HASH_MISMATCH, PatchReason.UNSUPPORTED_OPERATION}
)


def _iter_paragraph_bindings(ir: dict[str, Any]) -> Iterator[_ParagraphBinding]:
    """Yield physical paragraphs in story/block order without reclassifying them."""

    def walk(records: list[dict[str, Any]], story_id: str, part: str):
        for record in records:
            if not isinstance(record, dict):
                continue
            source_type = record.get("source_type")
            if source_type == "paragraph":
                yield _ParagraphBinding(story_id, part, record)
                continue
            children = record.get("children")
            if isinstance(children, list):
                yield from walk(children, story_id, part)

    for story in ir.get("stories") or []:
        story_id = story.get("story_id")
        part = story.get("part")
        if not isinstance(story_id, str) or not isinstance(part, str):
            continue
        blocks = story.get("blocks")
        if isinstance(blocks, list):
            yield from walk(blocks, story_id, part)


def _iter_runs(paragraph: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield decomposed run_raw descendants in PhysicalIR child order."""

    def walk(records: list[dict[str, Any]]):
        for record in records:
            if not isinstance(record, dict):
                continue
            if record.get("source_type") == "run_raw":
                yield record
                continue
            children = record.get("children")
            if isinstance(children, list):
                yield from walk(children)

    children = paragraph.get("children")
    if isinstance(children, list):
        yield from walk(children)


def _validate_api_inputs(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    max_applied_operations: int,
) -> None:
    if type(package_snapshot) is not bytes or not package_snapshot:
        raise ProcessingSessionContractError("package_snapshot must be non-empty bytes")
    if not isinstance(profile, ProcessingProfile):
        raise ProcessingSessionContractError("profile must be ProcessingProfile")
    if type(max_applied_operations) is not int or max_applied_operations <= 0:
        raise ProcessingSessionContractError(
            "max_applied_operations must be an exact positive int"
        )


def _build_decisions(
    ir: dict[str, Any],
    catalog: Any,
    classifications: tuple[ClassificationResult, ...],
    profile: ProcessingProfile,
) -> tuple[Decision, ...]:
    paragraph_index = {
        (binding.story_id, binding.paragraph.get("structural_path")): binding
        for binding in _iter_paragraph_bindings(ir)
    }
    decisions: list[Decision] = []
    canonical_bindings = profile.canonical_bindings

    for paragraph_result in classifications:
        if not eligible_for_automatic_use(paragraph_result):
            continue
        key = (paragraph_result.story_id, paragraph_result.structural_path)
        binding = paragraph_index.get(key)
        if binding is None:
            raise ProcessingSessionIntegrityError(
                "classified paragraph cannot be rebound to current PhysicalIR"
            )
        paragraph = binding.paragraph
        for run in _iter_runs(paragraph):
            run_result = project_run_classification(run, paragraph_result)
            if not eligible_for_automatic_use(run_result):
                continue
            if run_result.target_class is None:
                raise ProcessingSessionIntegrityError(
                    "eligible run classification lacks target_class"
                )
            target_class = run_result.target_class.value
            matching = tuple(
                b for b in canonical_bindings if b.target_class == target_class
            )
            if not matching:
                continue

            target_classification = project_target_classification(run_result)
            run_formatting = resolve_run_formatting(
                run, paragraph, catalog, binding.part
            )
            for rule_binding in matching:
                rule = rule_binding.rule
                decision_key = DecisionKey(
                    rule_binding.target_type, rule.aspect_id, rule.property_slot
                )
                resolved = extract_resolved_value(decision_key, run_formatting)
                context = DecisionContext(
                    decision_key, target_classification, profile.profile_ref
                )
                produced = evaluate_target(((rule, resolved, context),))
                if len(produced) != 1:
                    raise ProcessingSessionIntegrityError(
                        "single rule binding did not produce exactly one Decision"
                    )
                decisions.append(produced[0])

    return tuple(decisions)


def _evaluate(package_bytes: bytes, profile: ProcessingProfile) -> _EvaluationSnapshot:
    package_sha = hashlib.sha256(package_bytes).hexdigest()
    ir = DocxParser().parse_bytes(package_bytes)
    if not isinstance(ir, dict) or ir.get("status") != "ok":
        raise ProcessingSessionContractError(
            "package_snapshot cannot produce PhysicalIR status == ok"
        )
    if ir.get("package", {}).get("sha256") != package_sha:
        raise ProcessingSessionIntegrityError(
            "PhysicalIR package sha does not match evaluated package bytes"
        )

    catalog = build_style_catalog(package_bytes, ir)
    classifications = classify_document(ir, catalog)
    decisions = _build_decisions(ir, catalog, classifications, profile)

    source_document = source_document_ref_from_physical_ir(ir)
    upstream = UpstreamVersions(
        analysis_formatting_version=ANALYSIS_FORMATTING_VERSION,
        classification_version=CLASSIFICATION_VERSION,
        decision_version=DECISION_VERSION,
        decision_vocabulary_version=DECISION_VOCABULARY_VERSION,
    )
    plan = build_operation_plan(source_document, upstream, decisions)
    gate_report = evaluate_operation_plan(
        plan, decisions, ir, catalog, profile.profile_ref
    )
    if gate_report.current_package_sha256 != package_sha:
        raise ProcessingSessionIntegrityError(
            "SafetyGateReport does not bind the evaluated package snapshot"
        )
    return _EvaluationSnapshot(
        package_sha,
        ir,
        catalog,
        classifications,
        decisions,
        plan,
        gate_report,
    )


def _decision_order_maps(evaluation: _EvaluationSnapshot):
    by_decision_ref = {decision_ref(d): d for d in evaluation.decisions}
    if len(by_decision_ref) != len(evaluation.decisions):
        raise ProcessingSessionIntegrityError("duplicate canonical Decision refs in session")

    op_by_decision_ref = {op.decision_ref: op for op in evaluation.plan.operations}
    if len(op_by_decision_ref) != len(evaluation.plan.operations):
        raise ProcessingSessionIntegrityError(
            "multiple operations unexpectedly share a Decision ref"
        )

    token_by_decision_ref = {
        token.operation.decision_ref: token
        for token in evaluation.gate_report.cleared_operations
    }
    if len(token_by_decision_ref) != len(evaluation.gate_report.cleared_operations):
        raise ProcessingSessionIntegrityError(
            "multiple cleared tokens unexpectedly share a Decision ref"
        )
    return by_decision_ref, op_by_decision_ref, token_by_decision_ref


def _select_next(
    evaluation: _EvaluationSnapshot,
    rejected_on_snapshot: dict[str, Any],
):
    by_decision_ref, _, token_by_decision_ref = _decision_order_maps(evaluation)
    for ref in (decision_ref(d) for d in evaluation.decisions):
        token = token_by_decision_ref.get(ref)
        if token is None:
            continue
        if token.operation_ref in rejected_on_snapshot:
            continue
        decision = by_decision_ref.get(ref)
        if decision is None:
            raise ProcessingSessionIntegrityError(
                "cleared token cannot be rebound to generated Decision"
            )
        return token, decision
    return None


def _final_findings(
    evaluation: _EvaluationSnapshot,
    rejected_on_snapshot: dict[str, Any],
    *,
    operation_limit: bool,
) -> tuple[SessionFinding, ...]:
    _, op_by_decision_ref, token_by_decision_ref = _decision_order_maps(evaluation)
    gate_result_by_op_ref = {
        result.operation_ref: result for result in evaluation.gate_report.results
    }
    findings: list[SessionFinding] = []

    for decision in evaluation.decisions:
        dref = decision_ref(decision)
        operation = op_by_decision_ref.get(dref)
        if operation is None:
            continue
        opref = next(
            (
                ref
                for ref, result in gate_result_by_op_ref.items()
                if ref == getattr(result, "operation_ref", None)
                and any(
                    op is operation and candidate_ref == ref
                    for candidate_ref, op in (
                        (candidate_ref, candidate_op)
                        for candidate_ref, candidate_op in (
                            (r.operation_ref, p)
                            for r, p in zip(
                                evaluation.gate_report.results,
                                evaluation.plan.operations,
                            )
                        )
                    )
                )
            ),
            None,
        )
        # OperationPlan/gate result ordering is canonical and aligned; use a
        # direct lookup by canonical operation identity when the defensive
        # derivation above cannot establish it.
        if opref is None:
            from ..operation_plan import operation_ref as canonical_operation_ref

            opref = canonical_operation_ref(operation)

        rejected = rejected_on_snapshot.get(opref)
        if rejected is not None:
            if rejected.reason is None:
                raise ProcessingSessionIntegrityError(
                    "rejected PatchResult lacks rejection reason"
                )
            findings.append(
                SessionFinding(
                    SessionFindingKind.PATCH_REJECTED,
                    dref,
                    opref,
                    operation.target,
                    rejected.reason.value,
                )
            )
            continue

        gate_result = gate_result_by_op_ref.get(opref)
        if gate_result is None:
            raise ProcessingSessionIntegrityError(
                "planned operation has no SafetyGate result"
            )
        if gate_result.status is GateStatus.BLOCKED:
            if len(gate_result.reasons) != 1:
                raise ProcessingSessionIntegrityError(
                    "blocked GateResult lacks exactly one reason"
                )
            findings.append(
                SessionFinding(
                    SessionFindingKind.GATE_BLOCKED,
                    dref,
                    opref,
                    operation.target,
                    gate_result.reasons[0].value,
                )
            )
            continue

        if operation_limit and dref in token_by_decision_ref:
            findings.append(
                SessionFinding(
                    SessionFindingKind.OPERATION_LIMIT,
                    dref,
                    opref,
                    operation.target,
                    ProcessingSessionStatus.OPERATION_LIMIT_REACHED.value,
                )
            )

    return tuple(findings)


def _build_result(
    *,
    status: ProcessingSessionStatus,
    profile: ProcessingProfile,
    input_sha: str,
    current_bytes: bytes,
    transforms: list[Any],
    evaluation: _EvaluationSnapshot,
    rejected_on_snapshot: dict[str, Any],
    operation_limit: bool = False,
) -> ProcessingSessionResult:
    current_sha = hashlib.sha256(current_bytes).hexdigest()
    if current_sha != evaluation.package_sha256:
        raise ProcessingSessionIntegrityError(
            "terminal evaluation does not bind current output snapshot"
        )
    findings = _final_findings(
        evaluation, rejected_on_snapshot, operation_limit=operation_limit
    )
    return ProcessingSessionResult(
        processing_session_version=PROCESSING_SESSION_VERSION,
        status=status,
        profile_ref=profile.profile_ref,
        input_package_sha256=input_sha,
        output_package_sha256=current_sha,
        output_package_bytes=current_bytes,
        transforms=tuple(transforms),
        final_classifications=evaluation.classifications,
        final_decisions=evaluation.decisions,
        findings=findings,
    )


def process_document(
    package_snapshot: bytes,
    profile: ProcessingProfile,
    *,
    max_applied_operations: int = DEFAULT_MAX_APPLIED_OPERATIONS,
) -> ProcessingSessionResult:
    """Run the frozen safe pipeline until v0.1 automatic execution is quiescent."""

    _validate_api_inputs(package_snapshot, profile, max_applied_operations)
    input_sha = hashlib.sha256(package_snapshot).hexdigest()
    current_bytes = package_snapshot
    transforms: list[Any] = []
    seen_package_shas = {input_sha}
    rejected_on_snapshot: dict[str, Any] = {}

    while True:
        evaluation = _evaluate(current_bytes, profile)
        selected = _select_next(evaluation, rejected_on_snapshot)

        if selected is None:
            has_unapplied_deterministic = any(
                d.actionability is Actionability.DETERMINISTIC_CHANGE
                for d in evaluation.decisions
            )
            status = (
                ProcessingSessionStatus.QUIESCENT_WITH_UNAPPLIED
                if has_unapplied_deterministic
                else ProcessingSessionStatus.QUIESCENT
            )
            return _build_result(
                status=status,
                profile=profile,
                input_sha=input_sha,
                current_bytes=current_bytes,
                transforms=transforms,
                evaluation=evaluation,
                rejected_on_snapshot=rejected_on_snapshot,
            )

        token, source_decision = selected
        if len(transforms) >= max_applied_operations:
            return _build_result(
                status=ProcessingSessionStatus.OPERATION_LIMIT_REACHED,
                profile=profile,
                input_sha=input_sha,
                current_bytes=current_bytes,
                transforms=transforms,
                evaluation=evaluation,
                rejected_on_snapshot=rejected_on_snapshot,
                operation_limit=True,
            )

        patch_result = apply_cleared_operation(current_bytes, token)
        if patch_result.status is PatchStatus.REJECTED:
            if patch_result.reason in _IMPOSSIBLE_PATCH_REJECTIONS:
                raise ProcessingSessionIntegrityError(
                    f"impossible Patcher rejection inside bound session: {patch_result.reason.value}"
                )
            rejected_on_snapshot[token.operation_ref] = patch_result
            continue

        if patch_result.output_package_bytes is None or patch_result.output_package_sha256 is None:
            raise ProcessingSessionIntegrityError(
                "APPLIED PatchResult lacks output package provenance"
            )
        transform = build_transform_record(token, patch_result, source_decision)
        if transform.input_package_sha256 != evaluation.package_sha256:
            raise ProcessingSessionIntegrityError(
                "TransformRecord input does not bind current evaluation snapshot"
            )
        if transform.output_package_sha256 != patch_result.output_package_sha256:
            raise ProcessingSessionIntegrityError(
                "TransformRecord output does not bind PatchResult output"
            )

        next_sha = patch_result.output_package_sha256
        if next_sha in seen_package_shas:
            raise ProcessingSessionIntegrityError(
                "package SHA cycle detected across applied session transformations"
            )
        seen_package_shas.add(next_sha)
        transforms.append(transform)
        current_bytes = patch_result.output_package_bytes
        rejected_on_snapshot = {}
