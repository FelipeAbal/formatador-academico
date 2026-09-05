"""Decision Layer v0.1 vertical-slice contract tests."""
from __future__ import annotations
import os
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

from formatador_academico.analysis.formatting_model import (
    FormattingEvidence, Length, LineSpacing, ResolutionStatus, ResolvedValue,
)
from formatador_academico.decision import (
    Actionability, ComplianceStatus, Decision, DecisionContext, DecisionKey,
    DecisionReason, DecisionTarget, FormattingRule, LineSpacingValue,
    ProfileRef, RuleMode, TargetClassification, decide_property, evaluate_target,
    require_supported_key, serialize_decision, serialize_target_decisions,
    vocabulary_entry,
)


def _resolved(value, prop="w:x"):
    return ResolvedValue(
        status=ResolutionStatus.RESOLVED,
        value=value,
        winning_evidence=FormattingEvidence(
            source_kind="direct", part="word/document.xml", structural_path="/x",
            style_id=None, property_name=prop, raw_value=str(value),
        ),
        evidence_chain=(), reason=None,
    )


def _status_value(status):
    return ResolvedValue(status=status, value=None, winning_evidence=None,
                         evidence_chain=(), reason="x" if status is ResolutionStatus.UNRESOLVED else None)


def _run_context(key):
    return DecisionContext(
        key=key,
        classification=TargetClassification("run", "/p/r", "rh", "body", "fixture", "manual"),
        profile_ref=ProfileRef("profile", "1"),
    )


def _paragraph_context(key):
    return DecisionContext(
        key=key,
        classification=TargetClassification("paragraph", "/p", "ph", "body", "fixture", "manual"),
        profile_ref=ProfileRef("profile", "1"),
    )


class DecisionLayerV01Tests(unittest.TestCase):
    def test_exact_bold_match_and_mismatch(self):
        key = DecisionKey("run", "P1", "bold")
        ctx = _run_context(key)
        rule = FormattingRule("r", "P1", "bold", RuleMode.EXACT, expected=False)
        match = decide_property(rule, _resolved(False, "w:b"), ctx)
        self.assertEqual((match.compliance, match.actionability, match.reason),
                         (ComplianceStatus.COMPLIANT, Actionability.NO_ACTION, DecisionReason.MATCHES_RULE))
        mismatch = decide_property(rule, _resolved(True, "w:b"), ctx)
        self.assertEqual(mismatch.compliance, ComplianceStatus.NON_COMPLIANT)
        self.assertEqual(mismatch.actionability, Actionability.DETERMINISTIC_CHANGE)
        self.assertIs(mismatch.desired_value, False)

    def test_font_size_decimal_comparison(self):
        ctx = _run_context(DecisionKey("run", "P2", "font_size"))
        rule = FormattingRule("r", "P2", "font_size", RuleMode.EXACT, expected=Decimal("12"))
        match = decide_property(rule, _resolved(Length(Decimal("12.0"), "pt", "24", "half_point"), "w:sz"), ctx)
        self.assertEqual(match.compliance, ComplianceStatus.COMPLIANT)
        self.assertEqual(match.observed, Decimal("12.0"))
        mismatch = decide_property(rule, _resolved(Length(Decimal("11"), "pt", "22", "half_point"), "w:sz"), ctx)
        self.assertEqual(mismatch.desired_value, Decimal("12"))

    def test_alignment_literal_token_comparison(self):
        ctx = _paragraph_context(DecisionKey("paragraph", "P4", "alignment"))
        rule = FormattingRule("r", "P4", "alignment", RuleMode.EXACT, expected="both")
        self.assertEqual(decide_property(rule, _resolved("both", "w:jc"), ctx).compliance,
                         ComplianceStatus.COMPLIANT)
        self.assertEqual(decide_property(rule, _resolved("left", "w:jc"), ctx).desired_value, "both")

    def test_spacing_line_typed_comparison(self):
        ctx = _paragraph_context(DecisionKey("paragraph", "P3", "spacing.line"))
        expected = LineSpacingValue("auto", Decimal("1.5"), "multiple")
        rule = FormattingRule("r", "P3", "spacing.line", RuleMode.EXACT, expected=expected)
        match = LineSpacing("auto", Decimal("1.5"), "multiple", "360", None)
        self.assertEqual(decide_property(rule, _resolved(match, "w:spacing"), ctx).compliance,
                         ComplianceStatus.COMPLIANT)
        visual_guess = LineSpacing("exact", Decimal("18"), "pt", "360", "exact")
        self.assertEqual(decide_property(rule, _resolved(visual_guess, "w:spacing"), ctx).compliance,
                         ComplianceStatus.NON_COMPLIANT)

    def test_rule_absent_uses_explicit_decision_key(self):
        ctx = _run_context(DecisionKey("run", "P2", "font_size"))
        decision = decide_property(None, _status_value(ResolutionStatus.AMBIGUOUS), ctx)
        self.assertEqual((decision.target.aspect_id, decision.target.property_slot), ("P2", "font_size"))
        self.assertEqual((decision.compliance, decision.actionability, decision.reason),
                         (ComplianceStatus.NOT_APPLICABLE, Actionability.PRESERVE, DecisionReason.RULE_ABSENT))
        self.assertIsNone(decision.rule_ref)
        self.assertIsNone(decision.evidence_ref)
        self.assertEqual(decision.decision_warnings, ())

    def test_containment_preserves_without_observation_dependency(self):
        ctx = _run_context(DecisionKey("run", "P1", "bold"))
        rule = FormattingRule("r", "P1", "bold", RuleMode.CONTAINMENT)
        decision = decide_property(rule, _resolved(True, "w:b"), ctx)
        self.assertEqual((decision.compliance, decision.actionability, decision.reason),
                         (ComplianceStatus.NOT_EVALUATED, Actionability.PRESERVE, DecisionReason.CONTAINMENT))
        self.assertIsNotNone(decision.rule_ref)
        self.assertIsNone(decision.evidence_ref)
        self.assertIsNone(decision.desired_value)

    def test_analysis_status_matrix(self):
        ctx = _run_context(DecisionKey("run", "P1", "bold"))
        rule = FormattingRule("r", "P1", "bold", RuleMode.EXACT, expected=False)
        expected = {
            ResolutionStatus.ABSENT: DecisionReason.ANALYSIS_ABSENT,
            ResolutionStatus.UNRESOLVED: DecisionReason.ANALYSIS_UNRESOLVED,
            ResolutionStatus.INVALID: DecisionReason.ANALYSIS_INVALID,
            ResolutionStatus.AMBIGUOUS: DecisionReason.ANALYSIS_AMBIGUOUS,
        }
        for status, reason in expected.items():
            with self.subTest(status=status):
                decision = decide_property(rule, _status_value(status), ctx)
                self.assertEqual(decision.compliance, ComplianceStatus.UNKNOWN)
                self.assertEqual(decision.actionability, Actionability.REVIEW)
                self.assertEqual(decision.reason, reason)
                self.assertIsNone(decision.desired_value)

    def test_absent_bold_is_not_false(self):
        ctx = _run_context(DecisionKey("run", "P1", "bold"))
        rule = FormattingRule("r", "P1", "bold", RuleMode.EXACT, expected=False)
        decision = decide_property(rule, _status_value(ResolutionStatus.ABSENT), ctx)
        self.assertEqual(decision.compliance, ComplianceStatus.UNKNOWN)
        self.assertEqual(decision.reason, DecisionReason.ANALYSIS_ABSENT)

    def test_absent_spacing_is_review(self):
        ctx = _paragraph_context(DecisionKey("paragraph", "P3", "spacing.line"))
        rule = FormattingRule("r", "P3", "spacing.line", RuleMode.EXACT,
                              expected=LineSpacingValue("auto", Decimal("1.5"), "multiple"))
        decision = decide_property(rule, _status_value(ResolutionStatus.ABSENT), ctx)
        self.assertEqual((decision.compliance, decision.actionability),
                         (ComplianceStatus.UNKNOWN, Actionability.REVIEW))

    def test_set_mode_matrix(self):
        ctx = _run_context(DecisionKey("run", "P2", "font_size"))
        def rv(value):
            return _resolved(Length(Decimal(value), "pt", str(Decimal(value) * 2), "half_point"), "w:sz")
        no_pref = FormattingRule("r", "P2", "font_size", RuleMode.SET,
                                 allowed=(Decimal("11"), Decimal("12")))
        self.assertEqual(decide_property(no_pref, rv("11"), ctx).reason, DecisionReason.ALLOWED_VARIANT)
        outside = decide_property(no_pref, rv("14"), ctx)
        self.assertEqual((outside.compliance, outside.actionability, outside.reason),
                         (ComplianceStatus.NON_COMPLIANT, Actionability.HUMAN_CHOICE,
                          DecisionReason.HUMAN_CHOICE_REQUIRED))
        self.assertIsNone(outside.desired_value)
        preferred = FormattingRule("r", "P2", "font_size", RuleMode.SET,
                                   allowed=(Decimal("11"), Decimal("12")), preferred=Decimal("12"))
        self.assertEqual(decide_property(preferred, rv("12"), ctx).reason, DecisionReason.MATCHES_RULE)
        allowed_not_preferred = decide_property(preferred, rv("11"), ctx)
        self.assertEqual(allowed_not_preferred.reason, DecisionReason.PREFERRED_VARIANT_DIFFERS)
        self.assertEqual(allowed_not_preferred.desired_value, Decimal("12"))
        disallowed = decide_property(preferred, rv("14"), ctx)
        self.assertEqual(disallowed.reason, DecisionReason.DIFFERS_FROM_RULE)
        self.assertEqual(disallowed.desired_value, Decimal("12"))

    def test_desired_value_invariant_is_enforced_by_model(self):
        with self.assertRaises(ValueError):
            Decision("0.1", "0.1", DecisionTarget("run", "/x", "h", "body", "P1", "bold"),
                     ComplianceStatus.COMPLIANT, Actionability.NO_ACTION, DecisionReason.MATCHES_RULE,
                     "resolved", True, False, ProfileRef("p", "1"), None, None, ())

    def test_provenance_snapshots(self):
        ctx = _run_context(DecisionKey("run", "P1", "bold"))
        rule = FormattingRule("rule-1", "P1", "bold", RuleMode.EXACT, expected=False, path="/body/P1")
        decision = decide_property(rule, _resolved(True, "w:b"), ctx)
        self.assertEqual(decision.rule_ref.path, "/body/P1")
        self.assertEqual(decision.evidence_ref.property_name, "w:b")
        self.assertEqual(decision.target.physical_hash, "rh")
        self.assertEqual(decision.target.target_class, "body")

    def test_context_target_type_mismatch_is_contract_error(self):
        context = DecisionContext(
            DecisionKey("run", "P1", "bold"),
            TargetClassification("paragraph", "/p", "h", "body", "fixture"),
            ProfileRef("p", "1"),
        )
        with self.assertRaises(ValueError):
            decide_property(None, _resolved(True), context)

    def test_rule_key_mismatch_is_contract_error(self):
        ctx = _run_context(DecisionKey("run", "P1", "bold"))
        wrong = FormattingRule("r", "P2", "font_size", RuleMode.EXACT, expected=Decimal("12"))
        with self.assertRaises(ValueError):
            decide_property(wrong, _resolved(True), ctx)

    def test_vocabulary_registry_is_closed_for_slice(self):
        italic = DecisionKey("run", "P1", "italic")
        self.assertEqual(vocabulary_entry(italic).analysis_source, "ResolvedRunFormatting.italic")
        with self.assertRaises(ValueError):
            require_supported_key(italic)
        with self.assertRaises(ValueError):
            vocabulary_entry(DecisionKey("run", "P99", "unknown"))

    def test_evaluate_target_orders_and_preserves_partial_results(self):
        font_ctx = _run_context(DecisionKey("run", "P2", "font_size"))
        bold_ctx = _run_context(DecisionKey("run", "P1", "bold"))
        items = (
            (FormattingRule("f", "P2", "font_size", RuleMode.EXACT, expected=Decimal("12")),
             _resolved(Length(Decimal("12"), "pt", "24", "half_point"), "w:sz"), font_ctx),
            (FormattingRule("b", "P1", "bold", RuleMode.EXACT, expected=False),
             _resolved(True, "w:b"), bold_ctx),
        )
        decisions = evaluate_target(items)
        self.assertEqual([d.target.aspect_id for d in decisions], ["P1", "P2"])
        self.assertEqual(decisions[0].compliance, ComplianceStatus.NON_COMPLIANT)
        self.assertEqual(decisions[1].compliance, ComplianceStatus.COMPLIANT)

    def test_evaluate_target_rejects_multiple_targets(self):
        first = _run_context(DecisionKey("run", "P1", "bold"))
        second = DecisionContext(
            DecisionKey("run", "P2", "font_size"),
            TargetClassification("run", "/other", "h2", "body", "fixture"),
            ProfileRef("profile", "1"),
        )
        with self.assertRaises(ValueError):
            evaluate_target(((None, _resolved(True), first),
                             (None, _resolved(Length(Decimal("12"), "pt", "24", "half_point")), second)))

    def test_models_are_frozen(self):
        ctx = _run_context(DecisionKey("run", "P1", "bold"))
        rule = FormattingRule("r", "P1", "bold", RuleMode.EXACT, expected=True)
        decision = decide_property(rule, _resolved(True, "w:b"), ctx)
        with self.assertRaises(FrozenInstanceError):
            decision.compliance = ComplianceStatus.NON_COMPLIANT

    def test_rule_shapes_reject_invalid_prevalidated_inputs(self):
        with self.assertRaises(ValueError):
            FormattingRule("x", "P1", "bold", RuleMode.SET, allowed=())
        with self.assertRaises(ValueError):
            FormattingRule("x", "P1", "bold", RuleMode.SET, allowed=(True,), preferred=False)
        with self.assertRaises(ValueError):
            FormattingRule("x", "P1", "bold", RuleMode.EXACT, expected=None)

    def test_same_process_serialization_is_byte_stable(self):
        ctx = _run_context(DecisionKey("run", "P1", "bold"))
        rule = FormattingRule("r", "P1", "bold", RuleMode.EXACT, expected=False)
        decision = decide_property(rule, _resolved(True, "w:b"), ctx)
        self.assertEqual(serialize_decision(decision), serialize_decision(decision))
        self.assertIn(b'"decision_vocabulary_version":"0.1"', serialize_decision(decision))
        self.assertEqual(serialize_target_decisions((decision,)), serialize_target_decisions((decision,)))

    def test_cross_process_hashseed_determinism(self):
        repo = Path(__file__).resolve().parents[1]
        code = r'''from decimal import Decimal
from formatador_academico.analysis.formatting_model import FormattingEvidence, Length, ResolutionStatus, ResolvedValue
from formatador_academico.decision import *
ctx=DecisionContext(DecisionKey("run","P2","font_size"),TargetClassification("run","/p/r","h","body","fixture"),ProfileRef("p","1"))
rv=ResolvedValue(ResolutionStatus.RESOLVED,Length(Decimal("11"),"pt","22","half_point"),FormattingEvidence("direct","word/document.xml","/x",None,"w:sz","22"),(),None)
r=FormattingRule("r","P2","font_size",RuleMode.EXACT,expected=Decimal("12"))
print(serialize_decision(decide_property(r,rv,ctx)).hex())'''
        outputs = []
        for seed in ("0", "42"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = str(repo / "src")
            proc = subprocess.run([sys.executable, "-c", code], cwd=repo, env=env,
                                  capture_output=True, text=True, check=True)
            outputs.append(proc.stdout.strip())
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
