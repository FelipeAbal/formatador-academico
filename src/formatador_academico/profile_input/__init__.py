"""Profile Input / Form Schema v0.1 public API (decision 0040)."""
from .adapter import build_processing_profile
from .model import (
    MAX_DECIMAL_EXPONENT,
    MAX_DECIMAL_SIGNIFICANT_DIGITS,
    MAX_PROFILE_ID_CODEPOINTS,
    MAX_PROFILE_JSON_BYTES,
    MIN_DECIMAL_EXPONENT,
    PROFILE_INPUT_SCHEMA_VERSION,
    ProfileInput,
    ProfileInputContractError,
    ProfileInputError,
    ProfileInputRule,
    ProfileInputUnsupportedError,
    ProfileRuleMode,
    canonical_decimal,
)
from .parser import parse_profile_input_json


def processing_profile_from_json(profile_json_bytes: bytes):
    """Parse canonical Profile Input JSON bytes and build ProcessingProfile."""

    return build_processing_profile(parse_profile_input_json(profile_json_bytes))


__all__ = [
    "PROFILE_INPUT_SCHEMA_VERSION",
    "MAX_PROFILE_JSON_BYTES",
    "MAX_PROFILE_ID_CODEPOINTS",
    "MAX_DECIMAL_SIGNIFICANT_DIGITS",
    "MIN_DECIMAL_EXPONENT",
    "MAX_DECIMAL_EXPONENT",
    "ProfileInputError",
    "ProfileInputContractError",
    "ProfileInputUnsupportedError",
    "ProfileRuleMode",
    "ProfileInputRule",
    "ProfileInput",
    "canonical_decimal",
    "parse_profile_input_json",
    "build_processing_profile",
    "processing_profile_from_json",
]
