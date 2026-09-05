"""Decision Layer v0.1 public immutable models."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
from typing import Any

DECISION_VERSION = "0.1"

class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    NOT_EVALUATED = "not_evaluated"

class Actionability(str, Enum):
    NO_ACTION = "no_action"
    DETERMINISTIC_CHANGE = "deterministic_change"
    HUMAN_CHOICE = "human_choice"
    REVIEW = "review"
    PRESERVE = "preserve"

class DecisionReason(str, Enum):
    MATCHES_RULE = "matches_rule"
    DIFFERS_FROM_RULE = "differs_from_rule"
    ALLOWED_VARIANT = "allowed_variant"
    PREFERRED_VARIANT_DIFFERS = "preferred_variant_differs"
    HUMAN_CHOICE_REQUIRED = "human_choice_required"
    RULE_ABSENT = "rule_absent"
    CONTAINMENT = "containment"
    ANALYSIS_ABSENT = "analysis_absent"
    ANALYSIS_UNRESOLVED = "analysis_unresolved"
    ANALYSIS_INVALID = "analysis_invalid"
    ANALYSIS_AMBIGUOUS = "analysis_ambiguous"
    NOT_APPLICABLE = "not_applicable"

class RuleMode(str, Enum):
    EXACT = "exact"
    SET = "set"
    CONTAINMENT = "containment"

@dataclass(frozen=True)
class DecisionKey:
    target_type: str
    aspect_id: str
    property_slot: str

@dataclass(frozen=True)
class ProfileRef:
    profile_id: str
    profile_version: str

@dataclass(frozen=True)
class RuleRef:
    profile_id: str
    profile_version: str
    rule_id: str
    aspect_id: str
    path: str | None = None

@dataclass(frozen=True)
class TargetClassification:
    target_type: str
    structural_path: str
    physical_hash: str
    target_class: str
    classification_version: str
    provenance: str | None = None

@dataclass(frozen=True)
class DecisionContext:
    key: DecisionKey
    classification: TargetClassification
    profile_ref: ProfileRef

@dataclass(frozen=True)
class LineSpacingValue:
    rule: str
    value: Decimal | None
    unit: str | None

@dataclass(frozen=True)
class FormattingRule:
    rule_id: str
    aspect_id: str
    property_slot: str
    mode: RuleMode
    expected: Any = None
    allowed: tuple[Any, ...] = ()
    preferred: Any = None
    path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, RuleMode):
            raise TypeError("FormattingRule.mode must be RuleMode")
        if not isinstance(self.allowed, tuple):
            raise TypeError("FormattingRule.allowed must be a tuple")
        if self.mode is RuleMode.EXACT:
            if self.expected is None or self.allowed or self.preferred is not None:
                raise ValueError("exact rule requires expected only")
        elif self.mode is RuleMode.SET:
            if self.expected is not None or not self.allowed:
                raise ValueError("set rule requires non-empty allowed and no expected")
            if self.preferred is not None and self.preferred not in self.allowed:
                raise ValueError("preferred must be a member of allowed")
        elif self.mode is RuleMode.CONTAINMENT:
            if self.expected is not None or self.allowed or self.preferred is not None:
                raise ValueError("containment rule cannot carry expected/allowed/preferred")

@dataclass(frozen=True)
class DecisionTarget:
    target_type: str
    structural_path: str
    physical_hash: str
    target_class: str
    aspect_id: str
    property_slot: str

@dataclass(frozen=True)
class EvidenceRef:
    source_kind: str
    part: str
    structural_path: str
    style_id: str | None
    property_name: str
    raw_value: str | None

@dataclass(frozen=True)
class DecisionWarning:
    code: str
    message: str

@dataclass(frozen=True)
class Decision:
    decision_version: str
    decision_vocabulary_version: str
    target: DecisionTarget
    compliance: ComplianceStatus
    actionability: Actionability
    reason: DecisionReason
    analysis_status: str
    observed: Any
    desired_value: Any
    profile_ref: ProfileRef
    rule_ref: RuleRef | None
    evidence_ref: EvidenceRef | None
    decision_warnings: tuple[DecisionWarning, ...] = ()

    def __post_init__(self) -> None:
        has_desired = self.desired_value is not None
        should_have = self.actionability is Actionability.DETERMINISTIC_CHANGE
        if has_desired != should_have:
            raise ValueError("desired_value must exist iff actionability=deterministic_change")
