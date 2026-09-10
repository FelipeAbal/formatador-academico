"""Deterministic adapter from ProfileInput v0.3 to frozen ProcessingProfile."""
from __future__ import annotations

from ..decision import FormattingRule, ProfileRef, RuleMode
from ..processing_session import ProcessingProfile, RuleBinding
from .model import ProfileInput, ProfileInputContractError, ProfileInputRule, ProfileRuleMode

_PROPERTY_MAP = {
    "bold": ("run", "P1", "bold"),
    "font_size": ("run", "P2", "font_size"),
    "alignment": ("paragraph", "P4", "alignment"),
    "line_spacing": ("paragraph", "P3", "spacing.line"),
}


def _adapt_alignment(value: object) -> object:
    if value == "justify":
        return "both"
    return value


def _adapt_value(property_name: str, value: object) -> object:
    if property_name == "alignment":
        return _adapt_alignment(value)
    return value


def _formatting_rule(rule: ProfileInputRule) -> FormattingRule:
    target_type, aspect_id, property_slot = _PROPERTY_MAP[rule.property_name]
    del target_type  # mapping kept explicit; RuleBinding consumes it separately.
    rule_id = f"{rule.target_class}:{rule.property_name}"
    if rule.mode is ProfileRuleMode.EXACT:
        return FormattingRule(
            rule_id=rule_id,
            aspect_id=aspect_id,
            property_slot=property_slot,
            mode=RuleMode.EXACT,
            expected=_adapt_value(rule.property_name, rule.value),
            path=None,
        )
    if rule.mode is ProfileRuleMode.SET:
        return FormattingRule(
            rule_id=rule_id,
            aspect_id=aspect_id,
            property_slot=property_slot,
            mode=RuleMode.SET,
            allowed=tuple(_adapt_value(rule.property_name, value) for value in rule.allowed),
            preferred=_adapt_value(rule.property_name, rule.preferred) if rule.preferred is not None else None,
            path=None,
        )
    return FormattingRule(
        rule_id=rule_id,
        aspect_id=aspect_id,
        property_slot=property_slot,
        mode=RuleMode.CONTAINMENT,
        path=None,
    )


def build_processing_profile(profile_input: ProfileInput) -> ProcessingProfile:
    """Mechanically map an already-valid ProfileInput to ProcessingProfile."""

    if not isinstance(profile_input, ProfileInput):
        raise ProfileInputContractError(
            "profile_input_type", "profile_input must be a ProfileInput"
        )
    bindings = []
    for rule in profile_input.rules:
        target_type, _, _ = _PROPERTY_MAP[rule.property_name]
        bindings.append(
            RuleBinding(
                target_class=rule.target_class,
                target_type=target_type,
                rule=_formatting_rule(rule),
            )
        )
    return ProcessingProfile(
        ProfileRef(profile_input.profile_id, profile_input.profile_version),
        tuple(bindings),
    )
