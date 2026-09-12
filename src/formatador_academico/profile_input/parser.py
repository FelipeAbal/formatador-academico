"""Strict JSON parser for Profile Input / Form Schema v0.3 (decisions 0040, 0049 and 0051)."""
from __future__ import annotations

import json
from decimal import Decimal

from .model import (
    MAX_PROFILE_JSON_BYTES,
    PROFILE_INPUT_SCHEMA_VERSION,
    SUPPORTED_PROPERTIES_BY_SCHEMA_VERSION,
    ProfileInput,
    ProfileInputContractError,
    ProfileInputRule,
    ProfileInputUnsupportedError,
    ProfileRuleMode,
)

_TOP_FIELDS = frozenset({"schema_version", "profile", "rules"})
_PROFILE_FIELDS = frozenset({"id", "version"})
_RULE_FIELDS = frozenset({"mode", "value", "allowed", "preferred"})
_SUPPORTED_CLASSES = frozenset({"body", "heading"})
_SUPPORTED_MODES = {mode.value: mode for mode in ProfileRuleMode}
_MISSING = object()


def _contract(code: str, message: str):
    raise ProfileInputContractError(code, message)


def _unsupported(code: str, message: str):
    raise ProfileInputUnsupportedError(code, message)


def _pairs_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _contract("duplicate_key", f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(token: str):
    _contract("non_finite_number", f"non-finite JSON number is not allowed: {token}")


def _unknown_fields(obj: dict, allowed: frozenset[str], code: str) -> None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        _contract(code, f"unknown field: {unknown[0]}")


def _require_object(value, code: str, message: str) -> dict:
    if type(value) is not dict:
        _contract(code, message)
    return value


def _parse_rule(target_class: str, property_name: str, raw) -> ProfileInputRule:
    obj = _require_object(raw, "rule_type", "rule must be an object")
    _unknown_fields(obj, _RULE_FIELDS, "rule_unknown_field")

    mode_raw = obj.get("mode", _MISSING)
    if mode_raw is _MISSING:
        _contract("mode_missing", "rule mode is required")
    if type(mode_raw) is not str:
        _contract("mode_type", "rule mode must be a string")
    mode = _SUPPORTED_MODES.get(mode_raw)
    if mode is None:
        _unsupported("mode_unsupported", f"unsupported mode: {mode_raw}")

    # Explicit JSON null is never equivalent to field absence.
    for field in ("value", "allowed", "preferred"):
        if field in obj and obj[field] is None:
            _contract("null_not_allowed", f"null is not allowed for {field}")

    if mode is ProfileRuleMode.EXACT:
        if "value" not in obj:
            _contract("exact_value_missing", "exact mode requires value")
        if "allowed" in obj or "preferred" in obj:
            _contract("exact_shape", "exact mode accepts only value")
        return ProfileInputRule(target_class, property_name, mode, value=obj["value"])

    if mode is ProfileRuleMode.PRESERVE:
        if any(field in obj for field in ("value", "allowed", "preferred")):
            _contract("preserve_shape", "preserve mode accepts no payload")
        return ProfileInputRule(target_class, property_name, mode)

    if "value" in obj:
        _contract("set_shape", "set mode does not accept value")
    if "allowed" not in obj:
        _contract("set_allowed_missing", "set mode requires allowed")
    if type(obj["allowed"]) is not list:
        _contract("allowed_type", "allowed must be an array")
    preferred = obj.get("preferred", None)
    return ProfileInputRule(
        target_class,
        property_name,
        mode,
        allowed=tuple(obj["allowed"]),
        preferred=preferred,
    )


def parse_profile_input_json(profile_json_bytes: bytes) -> ProfileInput:
    """Parse canonical UTF-8 JSON bytes into a self-validating ProfileInput."""

    if type(profile_json_bytes) is not bytes:
        _contract("input_type", "profile JSON input must be exact bytes")
    if not profile_json_bytes:
        _contract("input_empty", "profile JSON input must not be empty")
    if len(profile_json_bytes) > MAX_PROFILE_JSON_BYTES:
        _contract("input_too_large", "profile JSON input exceeds 256 KiB")
    if profile_json_bytes.startswith(b"\xef\xbb\xbf"):
        _contract("utf8_bom", "UTF-8 BOM is not allowed")

    try:
        text = profile_json_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProfileInputContractError("utf8_invalid", "profile JSON must be strict UTF-8") from exc

    try:
        raw = json.loads(
            text,
            parse_float=Decimal,
            parse_int=Decimal,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs_object,
        )
    except ProfileInputContractError:
        raise
    except RecursionError as exc:
        raise ProfileInputContractError("json_too_deep", "profile JSON nesting is too deep") from exc
    except json.JSONDecodeError as exc:
        raise ProfileInputContractError("json_invalid", "profile JSON is invalid") from exc

    if type(raw) is not dict:
        _contract("top_level_type", "profile JSON top-level must be an object")

    # Version is intentionally checked before unknown-field validation so a
    # future schema carrying new fields is reported as unsupported, not malformed.
    schema_version = raw.get("schema_version", _MISSING)
    if schema_version is _MISSING:
        _contract("schema_version_missing", "schema_version is required")
    if type(schema_version) is not str:
        _contract("schema_version_type", "schema_version must be a string")
    if schema_version not in SUPPORTED_PROPERTIES_BY_SCHEMA_VERSION:
        _unsupported("schema_version_unsupported", f"unsupported schema_version: {schema_version}")

    supported_properties = SUPPORTED_PROPERTIES_BY_SCHEMA_VERSION[schema_version]
    _unknown_fields(raw, _TOP_FIELDS, "top_unknown_field")
    if "profile" not in raw:
        _contract("profile_missing", "profile is required")
    if "rules" not in raw:
        _contract("rules_missing", "rules is required")

    profile = _require_object(raw["profile"], "profile_type", "profile must be an object")
    _unknown_fields(profile, _PROFILE_FIELDS, "profile_unknown_field")
    if "id" not in profile:
        _contract("profile_id_missing", "profile.id is required")
    if "version" not in profile:
        _contract("profile_version_missing", "profile.version is required")

    rules_obj = _require_object(raw["rules"], "rules_type", "rules must be an object")
    if not rules_obj:
        _contract("rules_empty", "rules must contain at least one class")

    parsed_rules = []
    for target_class in sorted(rules_obj):
        if target_class not in _SUPPORTED_CLASSES:
            _unsupported("target_class_unsupported", f"unsupported target class: {target_class}")
        class_obj = _require_object(
            rules_obj[target_class], "class_type", "rule class must be an object"
        )
        if not class_obj:
            _contract("class_empty", f"rule class must not be empty: {target_class}")
        for property_name in sorted(class_obj):
            if property_name not in supported_properties:
                _unsupported("property_unsupported", f"property {property_name} is not supported in schema_version {schema_version}")
            parsed_rules.append(
                _parse_rule(target_class, property_name, class_obj[property_name])
            )

    try:
        return ProfileInput(
            schema_version=schema_version,
            profile_id=profile["id"],
            profile_version=profile["version"],
            rules=tuple(parsed_rules),
        )
    except RecursionError as exc:
        raise ProfileInputContractError("validation_too_deep", "profile validation is too deep") from exc
