"""Profile Input / Form Schema v0.1 immutable public models (decision 0040)."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from ..patcher import MAX_HALF_POINTS

PROFILE_INPUT_SCHEMA_VERSION = "0.1"
MAX_PROFILE_JSON_BYTES = 256 * 1024
MAX_PROFILE_ID_CODEPOINTS = 128
MAX_DECIMAL_SIGNIFICANT_DIGITS = 32
MIN_DECIMAL_EXPONENT = -16
MAX_DECIMAL_EXPONENT = 16

_SUPPORTED_CLASSES = frozenset({"body", "heading"})
_SUPPORTED_PROPERTIES = frozenset({"bold", "font_size"})


class ProfileInputError(ValueError):
    """Base error carrying a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ProfileInputContractError(ProfileInputError):
    """Malformed or internally contradictory user declaration."""


class ProfileInputUnsupportedError(ProfileInputError):
    """Well-formed declaration outside the v0.1 vocabulary/capability."""


class ProfileRuleMode(str, Enum):
    EXACT = "exact"
    SET = "set"
    PRESERVE = "preserve"


def _contract(code: str, message: str) -> None:
    raise ProfileInputContractError(code, message)


def _unsupported(code: str, message: str) -> None:
    raise ProfileInputUnsupportedError(code, message)


def validate_identity_string(name: str, value: object) -> str:
    if type(value) is not str:
        _contract(f"{name}_type", f"{name} must be a string")
    assert isinstance(value, str)
    if not value or len(value) > MAX_PROFILE_ID_CODEPOINTS:
        _contract(f"{name}_length", f"{name} must contain 1..128 code points")
    if value != value.strip():
        _contract(f"{name}_edge_whitespace", f"{name} must not have edge whitespace")
    for ch in value:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            _contract(f"{name}_surrogate", f"{name} must not contain surrogate code points")
        if unicodedata.category(ch) == "Cc":
            _contract(f"{name}_control", f"{name} must not contain control characters")
    return value


def canonical_decimal(value: object) -> Decimal:
    """Canonicalize a finite Decimal exactly, independent of global context."""

    if type(value) is not Decimal:
        _contract("font_size_type", "font_size must be a JSON number")
    assert isinstance(value, Decimal)
    if not value.is_finite():
        _contract("font_size_non_finite", "font_size must be finite")

    sign, digits, exponent = value.as_tuple()
    digits_list = list(digits)
    if not digits_list or all(d == 0 for d in digits_list):
        return Decimal("0")

    while len(digits_list) > 1 and digits_list[-1] == 0:
        digits_list.pop()
        exponent += 1

    canonical = Decimal((sign, tuple(digits_list), exponent))
    return canonical


def _decimal_capacity(value: Decimal) -> int:
    """Return exact half-points or raise; never multiply Decimal under context."""

    value = canonical_decimal(value)
    if value <= 0:
        _contract("font_size_non_positive", "font_size must be strictly positive")

    sign, digits, exponent = value.as_tuple()
    assert sign == 0
    if len(digits) > MAX_DECIMAL_SIGNIFICANT_DIGITS:
        _unsupported(
            "font_size_precision_unsupported",
            "font_size exceeds the v0.1 significant-digit capability",
        )
    if exponent < MIN_DECIMAL_EXPONENT or exponent > MAX_DECIMAL_EXPONENT:
        _unsupported(
            "font_size_exponent_unsupported",
            "font_size exponent is outside the v0.1 capability",
        )

    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit

    numerator = coefficient * 2
    if exponent >= 0:
        half_points = numerator * (10 ** exponent)
    else:
        denominator = 10 ** (-exponent)
        if numerator % denominator:
            _unsupported(
                "font_size_half_point_unsupported",
                "font_size is not exactly representable in half-points",
            )
        half_points = numerator // denominator

    if half_points > MAX_HALF_POINTS:
        _unsupported(
            "font_size_range_unsupported",
            "font_size exceeds the current Patcher range",
        )
    return half_points


def canonical_rule_value(property_name: str, value: object) -> object:
    if property_name == "bold":
        if type(value) is not bool:
            _contract("bold_type", "bold values must be JSON booleans")
        return value
    if property_name == "font_size":
        canonical = canonical_decimal(value)
        _decimal_capacity(canonical)
        return canonical
    _unsupported("property_unsupported", f"unsupported property: {property_name}")


@dataclass(frozen=True)
class ProfileInputRule:
    target_class: str
    property_name: str
    mode: ProfileRuleMode
    value: object | None = None
    allowed: tuple[object, ...] = ()
    preferred: object | None = None

    def __post_init__(self) -> None:
        if self.target_class not in _SUPPORTED_CLASSES:
            _unsupported("target_class_unsupported", f"unsupported target class: {self.target_class}")
        if self.property_name not in _SUPPORTED_PROPERTIES:
            _unsupported("property_unsupported", f"unsupported property: {self.property_name}")
        if not isinstance(self.mode, ProfileRuleMode):
            if type(self.mode) is str:
                _unsupported("mode_unsupported", f"unsupported mode: {self.mode}")
            _contract("mode_type", "mode must be a string")
        if not isinstance(self.allowed, tuple):
            _contract("allowed_type", "allowed must be an array")

        if self.mode is ProfileRuleMode.EXACT:
            if self.value is None:
                _contract("exact_value_missing", "exact mode requires value")
            if self.allowed or self.preferred is not None:
                _contract("exact_shape", "exact mode accepts only value")
            object.__setattr__(
                self, "value", canonical_rule_value(self.property_name, self.value)
            )
            return

        if self.mode is ProfileRuleMode.PRESERVE:
            if self.value is not None or self.allowed or self.preferred is not None:
                _contract("preserve_shape", "preserve mode accepts no payload")
            return

        if self.value is not None:
            _contract("set_shape", "set mode does not accept value")
        if not self.allowed:
            _contract("set_allowed_empty", "set mode requires non-empty allowed")
        canonical_allowed = tuple(
            canonical_rule_value(self.property_name, item) for item in self.allowed
        )
        if len(set(canonical_allowed)) != len(canonical_allowed):
            _contract("set_allowed_duplicate", "allowed contains semantic duplicates")
        canonical_preferred = None
        if self.preferred is not None:
            canonical_preferred = canonical_rule_value(self.property_name, self.preferred)
            if canonical_preferred not in canonical_allowed:
                _contract("set_preferred_not_allowed", "preferred must be a member of allowed")
        elif len(canonical_allowed) == 1:
            _contract(
                "set_singleton_without_preferred",
                "single-value set requires exact mode or an explicit preferred value",
            )
        object.__setattr__(self, "allowed", canonical_allowed)
        object.__setattr__(self, "preferred", canonical_preferred)

    @property
    def identity(self) -> tuple[str, str]:
        return (self.target_class, self.property_name)


@dataclass(frozen=True)
class ProfileInput:
    schema_version: str
    profile_id: str
    profile_version: str
    rules: tuple[ProfileInputRule, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not str:
            _contract("schema_version_type", "schema_version must be a string")
        if self.schema_version != PROFILE_INPUT_SCHEMA_VERSION:
            _unsupported(
                "schema_version_unsupported",
                f"unsupported schema_version: {self.schema_version}",
            )
        validate_identity_string("profile_id", self.profile_id)
        validate_identity_string("profile_version", self.profile_version)
        if not isinstance(self.rules, tuple):
            _contract("rules_type", "rules must be a tuple in the typed model")
        if not self.rules:
            _contract("rules_empty", "rules must contain at least one rule")
        if not all(isinstance(rule, ProfileInputRule) for rule in self.rules):
            _contract("rules_item_type", "rules must contain ProfileInputRule only")
        identities = tuple(rule.identity for rule in self.rules)
        if len(set(identities)) != len(identities):
            _contract("rules_duplicate_identity", "duplicate rule identity")
        canonical = tuple(sorted(self.rules, key=lambda r: r.identity))
        if self.rules != canonical:
            _contract("rules_not_canonical", "typed ProfileInput rules must be canonically ordered")
