"""Profile Input / Form Schema v0.1 tests (decision 0040)."""
from __future__ import annotations

import ast
import json
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal, getcontext, localcontext
from pathlib import Path

from formatador_academico.decision import RuleMode
from formatador_academico.patcher import MAX_HALF_POINTS
from formatador_academico.profile_input import (
    PROFILE_INPUT_SCHEMA_VERSION,
    ProfileInput,
    ProfileInputContractError,
    ProfileInputRule,
    ProfileInputUnsupportedError,
    ProfileRuleMode,
    build_processing_profile,
    canonical_decimal,
    parse_profile_input_json,
    processing_profile_from_json,
)


def _json(rules, *, profile_id="p", version="1", schema="0.1"):
    return json.dumps(
        {
            "schema_version": schema,
            "profile": {"id": profile_id, "version": version},
            "rules": rules,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _bold_exact(value=False):
    return {"body": {"bold": {"mode": "exact", "value": value}}}


class ProfileInputParsingTests(unittest.TestCase):
    def test_minimal_bold_exact(self):
        model = parse_profile_input_json(_json(_bold_exact()))
        self.assertEqual(model.schema_version, "0.1")
        self.assertEqual(model.rules[0].value, False)

    def test_schema_02_accepts_user_alignment_vocabulary(self):
        model = parse_profile_input_json(
            _json(
                {"body": {"alignment": {"mode": "exact", "value": "justify"}}},
                schema="0.2",
            )
        )
        self.assertEqual(model.schema_version, "0.2")
        self.assertEqual(model.rules[0].property_name, "alignment")
        self.assertEqual(model.rules[0].value, "justify")

    def test_schema_01_rejects_alignment(self):
        with self.assertRaises(ProfileInputUnsupportedError) as cm:
            parse_profile_input_json(
                _json(
                    {"body": {"alignment": {"mode": "exact", "value": "justify"}}},
                    schema="0.1",
                )
            )
        self.assertEqual(cm.exception.code, "property_unsupported")

    def test_schema_02_rejects_line_spacing_until_its_own_cycle(self):
        with self.assertRaises(ProfileInputUnsupportedError) as cm:
            parse_profile_input_json(
                _json(
                    {"body": {"line_spacing": {"mode": "exact", "value": 1.5}}},
                    schema="0.2",
                )
            )
        self.assertEqual(cm.exception.code, "property_unsupported")

    def test_body_heading_and_canonical_order(self):
        raw = _json(
            {
                "heading": {"font_size": {"mode": "exact", "value": 12}},
                "body": {"bold": {"mode": "exact", "value": False}},
            }
        )
        model = parse_profile_input_json(raw)
        self.assertEqual(
            tuple(r.identity for r in model.rules),
            (("body", "bold"), ("heading", "font_size")),
        )

    def test_external_type_empty_and_size_policy(self):
        for bad in ("{}", bytearray(b"{}"), memoryview(b"{}")):
            with self.subTest(type=type(bad).__name__):
                with self.assertRaises(ProfileInputContractError) as cm:
                    parse_profile_input_json(bad)  # type: ignore[arg-type]
                self.assertEqual(cm.exception.code, "input_type")
        with self.assertRaises(ProfileInputContractError) as cm:
            parse_profile_input_json(b"")
        self.assertEqual(cm.exception.code, "input_empty")
        with self.assertRaises(ProfileInputContractError) as cm:
            parse_profile_input_json(b" " * (256 * 1024 + 1))
        self.assertEqual(cm.exception.code, "input_too_large")

    def test_utf8_only_bom_utf16_utf32(self):
        text = _json(_bold_exact()).decode("utf-8")
        with self.assertRaises(ProfileInputContractError) as cm:
            parse_profile_input_json(b"\xef\xbb\xbf" + text.encode("utf-8"))
        self.assertEqual(cm.exception.code, "utf8_bom")
        for encoding in ("utf-16", "utf-32"):
            with self.subTest(encoding=encoding):
                with self.assertRaises(ProfileInputContractError):
                    parse_profile_input_json(text.encode(encoding))

    def test_invalid_json_top_level_and_trailing(self):
        for raw in (b"{", b"[]", _json(_bold_exact()) + b" x"):
            with self.subTest(raw=raw[:10]):
                with self.assertRaises(ProfileInputContractError):
                    parse_profile_input_json(raw)

    def test_duplicate_keys_all_levels(self):
        docs = [
            b'{"schema_version":"0.1","schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":{"mode":"exact","value":false}}}}',
            b'{"schema_version":"0.1","profile":{"id":"p","id":"q","version":"1"},"rules":{"body":{"bold":{"mode":"exact","value":false}}}}',
            b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":{"mode":"exact","value":false},"bold":{"mode":"exact","value":true}}}}',
            b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":{"mode":"exact","mode":"preserve","value":false}}}}',
        ]
        for raw in docs:
            with self.subTest(raw=raw):
                with self.assertRaises(ProfileInputContractError) as cm:
                    parse_profile_input_json(raw)
                self.assertEqual(cm.exception.code, "duplicate_key")

    def test_schema_version_precedes_unknown_field(self):
        raw = b'{"schema_version":"0.3","new_future_field":1}'
        with self.assertRaises(ProfileInputUnsupportedError) as cm:
            parse_profile_input_json(raw)
        self.assertEqual(cm.exception.code, "schema_version_unsupported")

    def test_unknown_fields_and_structural_types(self):
        cases = [
            b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":{"mode":"exact","value":false}}},"x":1}',
            b'{"schema_version":"0.1","profile":{"id":"p","version":"1","x":1},"rules":{"body":{"bold":{"mode":"exact","value":false}}}}',
            b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":{"mode":"exact","value":false,"x":1}}}}',
            b'{"schema_version":"0.1","profile":[],"rules":{}}',
            b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":[]}',
            b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":[]}}',
            b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"bold":true}}}',
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(ProfileInputContractError):
                    parse_profile_input_json(raw)

    def test_unknown_vocabulary_is_unsupported(self):
        cases = [
            _json({"reference": {"bold": {"mode": "exact", "value": False}}}),
            _json({"body": {"italic": {"mode": "exact", "value": False}}}),
            _json({"body": {"bold": {"mode": "magic", "value": False}}}),
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(ProfileInputUnsupportedError):
                    parse_profile_input_json(raw)

    def test_null_is_never_absence(self):
        for rule in (
            {"mode": "exact", "value": None},
            {"mode": "set", "allowed": [True, False], "preferred": None},
            {"mode": "preserve", "value": None},
        ):
            with self.subTest(rule=rule):
                with self.assertRaises(ProfileInputContractError) as cm:
                    parse_profile_input_json(_json({"body": {"bold": rule}}))
                self.assertEqual(cm.exception.code, "null_not_allowed")

    def test_non_finite_literals(self):
        for token in (b"NaN", b"Infinity", b"-Infinity"):
            raw = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"font_size":{"mode":"exact","value":' + token + b'}}}}'
            with self.subTest(token=token):
                with self.assertRaises(ProfileInputContractError) as cm:
                    parse_profile_input_json(raw)
                self.assertEqual(cm.exception.code, "non_finite_number")


class ProfileIdentityTests(unittest.TestCase):
    def test_identity_lexical_rules(self):
        bad_ids = ("", " x", "x ", "a\n", "\ud800", "x" * 129)
        for value in bad_ids:
            with self.subTest(value=repr(value)):
                raw_text = json.dumps(
                    {
                        "schema_version": "0.1",
                        "profile": {"id": value, "version": "1"},
                        "rules": _bold_exact(),
                    },
                    ensure_ascii=True,
                )
                with self.assertRaises(ProfileInputContractError):
                    parse_profile_input_json(raw_text.encode("utf-8"))

    def test_unicode_is_not_normalized(self):
        composed = parse_profile_input_json(_json(_bold_exact(), profile_id="café"))
        decomposed = parse_profile_input_json(_json(_bold_exact(), profile_id="cafe\u0301"))
        self.assertNotEqual(composed.profile_id, decomposed.profile_id)


class DecimalAdversarialTests(unittest.TestCase):
    def test_canonical_numeric_spellings(self):
        models = []
        for token in (b"12", b"12.0", b"1.2e1"):
            raw = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"font_size":{"mode":"exact","value":' + token + b'}}}}'
            models.append(parse_profile_input_json(raw))
        self.assertEqual(models[0], models[1])
        self.assertEqual(models[1], models[2])
        self.assertEqual(models[0].rules[0].value, Decimal("12"))
        self.assertEqual(
            build_processing_profile(models[0]), build_processing_profile(models[1])
        )

    def test_decimal_trailing_zero_canonicalization(self):
        self.assertEqual(canonical_decimal(Decimal("11.50")), Decimal("11.5"))
        self.assertEqual(canonical_decimal(Decimal("12.000")), Decimal("12"))

    def test_half_point_exactness(self):
        good = parse_profile_input_json(_json({"body": {"font_size": {"mode": "exact", "value": 11.5}}}))
        self.assertEqual(good.rules[0].value, Decimal("11.5"))
        with self.assertRaises(ProfileInputUnsupportedError) as cm:
            parse_profile_input_json(_json({"body": {"font_size": {"mode": "exact", "value": 11.25}}}))
        self.assertEqual(cm.exception.code, "font_size_half_point_unsupported")

    def test_adversarial_decimal_does_not_round_under_default_context(self):
        raw = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"font_size":{"mode":"exact","value":1.000000000000000000000000000005}}}}'
        with self.assertRaises(ProfileInputUnsupportedError):
            parse_profile_input_json(raw)

    def test_decimal_context_independence(self):
        raw = _json({"body": {"font_size": {"mode": "exact", "value": 11.5}}})
        baseline = parse_profile_input_json(raw)
        old = getcontext().prec
        try:
            getcontext().prec = 3
            altered = parse_profile_input_json(raw)
        finally:
            getcontext().prec = old
        self.assertEqual(baseline, altered)

    def test_range_and_precision_caps(self):
        with self.assertRaises(ProfileInputUnsupportedError) as cm:
            parse_profile_input_json(_json({"body": {"font_size": {"mode": "exact", "value": 2000}}}))
        self.assertEqual(cm.exception.code, "font_size_range_unsupported")
        raw = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"font_size":{"mode":"exact","value":123456789012345678901234567890123}}}}'
        with self.assertRaises(ProfileInputUnsupportedError):
            parse_profile_input_json(raw)

    def test_zero_negative_are_contract_errors(self):
        for value in (0, -1):
            with self.subTest(value=value):
                with self.assertRaises(ProfileInputContractError) as cm:
                    parse_profile_input_json(_json({"body": {"font_size": {"mode": "exact", "value": value}}}))
                self.assertEqual(cm.exception.code, "font_size_non_positive")

    def test_shared_patcher_capacity_symbol(self):
        self.assertEqual(MAX_HALF_POINTS, 3276)


class ModeAndModelInvariantTests(unittest.TestCase):
    def test_preserve_and_shapes(self):
        rule = parse_profile_input_json(_json({"body": {"bold": {"mode": "preserve"}}})).rules[0]
        self.assertIs(rule.mode, ProfileRuleMode.PRESERVE)
        for bad in (
            {"mode": "exact", "value": False, "preferred": False},
            {"mode": "preserve", "allowed": [True]},
            {"mode": "set", "allowed": []},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ProfileInputContractError):
                    parse_profile_input_json(_json({"body": {"bold": bad}}))

    def test_set_semantics_and_singleton_policy(self):
        valid = parse_profile_input_json(
            _json({"body": {"bold": {"mode": "set", "allowed": [True, False], "preferred": False}}})
        )
        self.assertEqual(valid.rules[0].allowed, (True, False))
        with self.assertRaises(ProfileInputContractError) as cm:
            parse_profile_input_json(_json({"body": {"bold": {"mode": "set", "allowed": [False]}}}))
        self.assertEqual(cm.exception.code, "set_singleton_without_preferred")
        accepted = parse_profile_input_json(
            _json({"body": {"bold": {"mode": "set", "allowed": [False], "preferred": False}}})
        )
        self.assertEqual(accepted.rules[0].preferred, False)

    def test_semantic_duplicate_allowed_after_decimal_canonicalization(self):
        raw = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"font_size":{"mode":"set","allowed":[12,12.0],"preferred":12}}}}'
        with self.assertRaises(ProfileInputContractError) as cm:
            parse_profile_input_json(raw)
        self.assertEqual(cm.exception.code, "set_allowed_duplicate")

    def test_models_are_frozen_and_programmatic_validation_is_real(self):
        rule = ProfileInputRule("body", "bold", ProfileRuleMode.EXACT, value=False)
        model = ProfileInput("0.1", "p", "1", (rule,))
        with self.assertRaises(FrozenInstanceError):
            model.profile_id = "x"  # type: ignore[misc]
        with self.assertRaises(ProfileInputUnsupportedError):
            ProfileInputRule("body", "font_size", ProfileRuleMode.EXACT, value=Decimal("11.25"))
        with self.assertRaises(ProfileInputContractError):
            ProfileInput("0.1", "p", "1", (rule, rule))

    def test_typed_model_requires_canonical_rule_order(self):
        a = ProfileInputRule("body", "bold", ProfileRuleMode.EXACT, value=False)
        b = ProfileInputRule("heading", "bold", ProfileRuleMode.EXACT, value=False)
        with self.assertRaises(ProfileInputContractError) as cm:
            ProfileInput("0.1", "p", "1", (b, a))
        self.assertEqual(cm.exception.code, "rules_not_canonical")


class AdapterTests(unittest.TestCase):
    def test_adapter_mapping_ids_and_modes(self):
        model = parse_profile_input_json(
            _json(
                {
                    "body": {
                        "bold": {"mode": "exact", "value": False},
                        "font_size": {"mode": "set", "allowed": [11, 12], "preferred": 12},
                    },
                    "heading": {"bold": {"mode": "preserve"}},
                }
            )
        )
        profile = build_processing_profile(model)
        self.assertEqual(profile.profile_ref.profile_id, "p")
        by_id = {b.rule.rule_id: b for b in profile.bindings}
        self.assertEqual(set(by_id), {"body:bold", "body:font_size", "heading:bold"})
        self.assertIs(by_id["body:bold"].rule.mode, RuleMode.EXACT)
        self.assertIs(by_id["body:font_size"].rule.mode, RuleMode.SET)
        self.assertIs(by_id["heading:bold"].rule.mode, RuleMode.CONTAINMENT)
        self.assertEqual(by_id["body:font_size"].rule.preferred, Decimal("12"))
        self.assertIsNone(by_id["body:bold"].rule.path)

    def test_no_absent_binding_or_cross_class_inheritance(self):
        profile = processing_profile_from_json(_json({"body": {"font_size": {"mode": "exact", "value": 12}}}))
        self.assertEqual(len(profile.bindings), 1)
        self.assertEqual(profile.bindings[0].target_class, "body")
        self.assertEqual(profile.bindings[0].rule.property_slot, "font_size")

    def test_key_order_and_numeric_lexical_equivalence(self):
        a = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"body":{"font_size":{"mode":"exact","value":12.0},"bold":{"mode":"exact","value":false}}}}'
        b = b'{"rules":{"body":{"bold":{"value":false,"mode":"exact"},"font_size":{"value":1.2e1,"mode":"exact"}}},"profile":{"version":"1","id":"p"},"schema_version":"0.1"}'
        self.assertEqual(processing_profile_from_json(a), processing_profile_from_json(b))

    def test_wrong_adapter_type(self):
        with self.assertRaises(ProfileInputContractError) as cm:
            build_processing_profile(object())  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, "profile_input_type")


class DeterminismAndStaticAuditTests(unittest.TestCase):
    def test_error_code_is_stable_with_multiple_errors(self):
        raw = b'{"schema_version":"0.1","profile":{"id":"p","version":"1"},"rules":{"zzz":{},"body":{"zzz":{"mode":"bad"}}}}'
        codes = []
        for _ in range(5):
            with self.assertRaises(ProfileInputUnsupportedError) as cm:
                parse_profile_input_json(raw)
            codes.append(cm.exception.code)
        self.assertEqual(codes, ["property_unsupported"] * 5)

    def test_runtime_has_no_forbidden_authority_imports_or_io(self):
        root = Path("src/formatador_academico/profile_input")
        forbidden_calls = {"open", "eval", "exec"}
        forbidden_import_roots = {"requests", "urllib", "socket", "random", "time", "datetime", "subprocess", "os"}
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = []
                    if isinstance(node, ast.Import):
                        names = [alias.name.split(".")[0] for alias in node.names]
                    elif node.module:
                        names = [node.module.split(".")[0]]
                    self.assertTrue(forbidden_import_roots.isdisjoint(names), (path, names))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, forbidden_calls, path)
