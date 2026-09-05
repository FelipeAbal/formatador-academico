"""Pure deterministic Decision Layer v0.1 engine."""
from __future__ import annotations
from decimal import Decimal
from typing import Any
from ..analysis.formatting_model import Length, LineSpacing, ResolutionStatus, ResolvedValue
from .model import (
    DECISION_VERSION, Actionability, ComplianceStatus, Decision, DecisionContext,
    DecisionReason, DecisionTarget, EvidenceRef, FormattingRule, LineSpacingValue,
    RuleMode, RuleRef,
)
from .vocabulary import DECISION_VOCABULARY_VERSION, require_supported_key

_STATUS_REASON = {
    ResolutionStatus.ABSENT: DecisionReason.ANALYSIS_ABSENT,
    ResolutionStatus.UNRESOLVED: DecisionReason.ANALYSIS_UNRESOLVED,
    ResolutionStatus.INVALID: DecisionReason.ANALYSIS_INVALID,
    ResolutionStatus.AMBIGUOUS: DecisionReason.ANALYSIS_AMIGUOUS if False else DecisionReason.ANALYSIS_AMBIGUOUS,
}

def _validate_context(context: DecisionContext) -> None:
    require_supported_key(context.key)
    c = context.classification
    if c.target_type != context.key.target_type:
        raise ValueError("classification target_type does not match DecisionKey")
    if not c.structural_path or not c.physical_hash or not c.target_class:
        raise ValueError("classification lacks required target provenance")

def _validate_rule(rule: FormattingRule, context: DecisionContext) -> None:
    if rule.aspect_id != context.key.aspect_id or rule.property_slot != context.key.property_slot:
        raise ValueError("rule aspect/property does not match DecisionKey")

def _target(context: DecisionContext) -> DecisionTarget:
    c = context.classification
    k = context.key
    return DecisionTarget(c.target_type, c.structural_path, c.physical_hash, c.target_class, k.aspect_id, k.property_slot)

def _rule_ref(rule: FormattingRule, context: DecisionContext) -> RuleRef:
    p = context.profile_ref
    return RuleRef(p.profile_id, p.profile_version, rule.rule_id, rule.aspect_id, rule.path)

def _evidence_ref(resolved: ResolvedValue) -> EvidenceRef | None:
    e = resolved.winning_evidence
    if e is None:
        return None
    return EvidenceRef(e.source_kind, e.part, e.structural_path, e.style_id, e.property_name, e.raw_value)

def _semantic_value(slot: str, value: Any) -> Any:
    if slot == "bold":
        if not isinstance(value, bool):
            raise ValueError("resolved bold must be bool")
        return value
    if slot == "font_size":
        if not isinstance(value, Length) or value.unit != "pt":
            raise ValueError("resolved font_size must be Length in pt")
        return value.value
    if slot == "alignment":
        if not isinstance(value, str):
            raise ValueError("resolved alignment must be str")
        return value
    if slot == "spacing.line":
        if not isinstance(value, LineSpacing):
            raise ValueError("resolved spacing.line must be LineSpacing")
        return LineSpacingValue(value.rule, value.value, value.unit)
    raise ValueError(f"unsupported property slot: {slot}")

def _validate_rule_value(slot: str, value: Any) -> None:
    if slot == "bold" and not isinstance(value, bool):
        raise ValueError("bold rule value must be bool")
    if slot == "font_size" and not isinstance(value, Decimal):
        raise ValueError("font_size rule value must be Decimal points")
    if slot == "alignment" and not isinstance(value, str):
        raise ValueError("alignment rule value must be canonical str token")
    if slot == "spacing.line" and not isinstance(value, LineSpacingValue):
        raise ValueError("spacing.line rule value must be LineSpacingValue")

def _validate_rule_values(rule: FormattingRule, slot: str) -> None:
    if rule.mode is RuleMode.EXACT:
        _validate_rule_value(slot, rule.expected)
    elif rule.mode is RuleMode.SET:
        for value in rule.allowed:
            _validate_rule_value(slot, value)
        if rule.preferred is not None:
            _validate_rule_value(slot, rule.preferred)

def _decision(context: DecisionContext, resolved: ResolvedValue, *, compliance: ComplianceStatus,
              actionability: Actionability, reason: DecisionReason, observed: Any = None,
              desired: Any = None, rule_ref: RuleRef | None = None,
              evidence_ref: EvidenceRef | None = None) -> Decision:
    return Decision(
        DECISION_VERSION, DECISION_VOCABULARY_VERSION, _target(context), compliance,
        actionability, reason, resolved.status.value, observed, desired,
        context.profile_ref, rule_ref, evidence_ref, (),
    )

def decide_property(rule_or_none: FormattingRule | None, resolved: ResolvedValue,
                    context: DecisionContext) -> Decision:
    _validate_context(context)
    if rule_or_none is None:
        return _decision(
            context, resolved, compliance=ComplianceStatus.NOT_APPLICABLE,
            actionability=Actionability.PRESERVE, reason=DecisionReason.RULE_ABSENT,
        )

    rule = rule_or_none
    _validate_rule(rule, context)
    _validate_rule_values(rule, context.key.property_slot)
    ref = _rule_ref(rule, context)

    if rule.mode is RuleMode.CONTAINMENT:
        return _decision(
            context, resolved, compliance=ComplianceStatus.NOT_EVALUATED,
            actionability=Actionability.PRESERVE, reason=DecisionReason.CONTAINMENT,
            rule_ref=ref,
        )

    if resolved.status is not ResolutionStatus.RESOLVED:
        try:
            reason = _STATUS_REASON[resolved.status]
        except KeyError as exc:
            raise ValueError(f"unknown analysis status: {resolved.status}") from exc
        return _decision(
            context, resolved, compliance=ComplianceStatus.UNKNOWN,
            actionability=Actionability.REVIEW, reason=reason, rule_ref=ref,
        )

    observed = _semantic_value(context.key.property_slot, resolved.value)
    evidence = _evidence_ref(resolved)

    if rule.mode is RuleMode.EXACT:
        if observed == rule.expected:
            return _decision(
                context, resolved, compliance=ComplianceStatus.COMPLIANT,
                actionability=Actionability.NO_ACTION, reason=DecisionReason.MATCHES_RULE,
                observed=observed, rule_ref=ref, evidence_ref=evidence,
            )
        return _decision(
            context, resolved, compliance=ComplianceStatus.NON_COMPLIANT,
            actionability=Actionability.DETERMINISTIC_CHANGE,
            reason=DecisionReason.DIFFERS_FROM_RULE, observed=observed,
            desired=rule.expected, rule_ref=ref, evidence_ref=evidence,
        )

    if rule.mode is RuleMode.SET:
        in_allowed = observed in rule.allowed
        if in_allowed and rule.preferred is None:
            return _decision(
                context, resolved, compliance=ComplianceStatus.COMPLIANT,
                actionability=Actionability.NO_ACTION, reason=DecisionReason.ALLOWED_VARIANT,
                observed=observed, rule_ref=ref, evidence_ref=evidence,
            )
        if in_allowed and observed == rule.preferred:
            return _decision(
                context, resolved, compliance=ComplianceStatus.COMPLIANT,
                actionability=Actionability.NO_ACTION, reason=DecisionReason.MATCHES_RULE,
                observed=observed, rule_ref=ref, evidence_ref=evidence,
            )
        if rule.preferred is not None:
            reason = DecisionReason.PREFERRED_VARIANT_DIFFERS if in_allowed else DecisionReason.DIFFERS_FROM_RULE
            return _decision(
                context, resolved, compliance=ComplianceStatus.NON_COMPLIANT,
                actionability=Actionability.DETERMINISTIC_CHANGE, reason=reason,
                observed=observed, desired=rule.preferred, rule_ref=ref, evidence_ref=evidence,
            )
        return _decision(
            context, resolved, compliance=ComplianceStatus.NON_COMPLIANT,
            actionability=Actionability.HUMAN_CHOICE,
            reason=DecisionReason.HUMAN_CHOICE_REQUIRED, observed=observed,
            rule_ref=ref, evidence_ref=evidence,
        )

    raise AssertionError("unreachable validated rule mode")

def evaluate_target(items: tuple[tuple[FormattingRule | None, ResolvedValue, DecisionContext], ...]) -> tuple[Decision, ...]:
    if not isinstance(items, tuple):
        raise TypeError("evaluate_target items must be a tuple")
    decisions = [decide_property(rule, resolved, context) for rule, resolved, context in items]
    first_target = None
    for decision in decisions:
        target_identity = (
            decision.target.target_type, decision.target.structural_path,
            decision.target.physical_hash, decision.target.target_class,
        )
        if first_target is None:
            first_target = target_identity
        elif target_identity != first_target:
            raise ValueError("evaluate_target received more than one physical/classified target")
    decisions.sort(key=lambda d: (d.target.aspect_id, d.target.property_slot))
    return tuple(decisions)
