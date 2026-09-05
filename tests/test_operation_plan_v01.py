"""OperationPlan v0.1 — unit/contract tests.

Contract: docs/decisions/0024-operation-plan-v01-contract.md.
Covers the mandatory minimum test list (briefing item 60).
"""

from __future__ import annotations

import copy
import hashlib
import os
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

from formatador_academico.decision import (
    Actionability,
    ComplianceStatus,
    Decision,
    DecisionReason,
    DecisionTarget,
    LineSpacingValue,
    ProfileRef,
    RuleRef,
    serialize_decision,
)
from formatador_academico.operation_plan import (
    OPERATION_PLAN_VERSION,
    OPERATION_VOCABULARY_VERSION,
    PLANNED_STORY_PART,
    LengthValue,
    OperationKind,
    OperationPlanAggregationError,
    OperationPlanContractError,
    OperationTarget,
    PlanningStatus,
    SourceDocumentRef,
    UpstreamVersions,
    build_operation_plan,
    plan_decision,
    serialize_operation_plan,
)

PROFILE = ProfileRef("perfil-teste", "1")
UPSTREAM = UpstreamVersions("0.1b-m2", "0.1", "0.1", "0.1")
SOURCE = SourceDocumentRef("a" * 64, "0.4.0")


def _target(target_type="run", aspect="P1", slot="bold", path="p[0]/r[0]",
            physical_hash="h" * 16, target_class="body"):
    return DecisionTarget(target_type, path, physical_hash, target_class, aspect, slot)


def _rule_ref(aspect="P1", rule_id="r-1"):
    return RuleRef(PROFILE.profile_id, PROFILE.profile_version, rule_id, aspect)


def _decision(actionability, reason, observed=None, desired=None, rule_ref=None,
              target=None, compliance=ComplianceStatus.NON_COMPLIANT,
              analysis_status="resolved"):
    return Decision(
        decision_version="0.1",
        decision_vocabulary_version="0.1",
        target=target if target is not None else _target(),
        compliance=compliance,
        actionability=actionability,
        reason=reason,
        analysis_status=analysis_status,
        observed=observed,
        desired_value=desired,
        profile_ref=PROFILE,
        rule_ref=rule_ref,
        evidence_ref=None,
    )


def _bold_deterministic():
    return _decision(
        Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
        observed=True, desired=False, rule_ref=_rule_ref("P1"),
        target=_target("run", "P1", "bold"),
    )


def _font_deterministic():
    return _decision(
        Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
        observed=Decimal("11"), desired=Decimal("12"), rule_ref=_rule_ref("P2"),
        target=_target("run", "P2", "font_size"),
    )


def _spacing_no_action():
    value = LineSpacingValue("auto", Decimal("1.5"), "multiple")
    return _decision(
        Actionability.NO_ACTION, DecisionReason.MATCHES_RULE,
        observed=value, rule_ref=_rule_ref("P3", "r-3"),
        target=_target("paragraph", "P3", "spacing.line", path="p[0]"),
        compliance=ComplianceStatus.COMPLIANT,
    )


def _alignment_review():
    return _decision(
        Actionability.REVIEW, DecisionReason.ANALYSIS_UNRESOLVED,
        observed=None, rule_ref=_rule_ref("P4", "r-4"),
        target=_target("paragraph", "P4", "alignment", path="p[0]"),
        compliance=ComplianceStatus.UNKNOWN, analysis_status="unresolved",
    )


class TestPlannedOperations(unittest.TestCase):
    # item 60.1 — deterministic bold -> planned
    def test_deterministic_bold_planned(self):
        result = plan_decision(_bold_deterministic())
        self.assertEqual(result.status, PlanningStatus.PLANNED)
        op = result.operation
        self.assertIsNotNone(op)
        self.assertEqual(op.kind, OperationKind.SET_PROPERTY)
        self.assertEqual((op.key.target_type, op.key.aspect_id, op.key.property_slot),
                         ("run", "P1", "bold"))
        self.assertIs(op.precondition_observed, True)
        self.assertIs(op.desired_value, False)
        self.assertEqual(result.decision_actionability, "deterministic_change")
        self.assertEqual(result.decision_reason, "differs_from_rule")

    # item 60.2 — deterministic font size -> planned, typed pt, no half-points
    def test_deterministic_font_size_planned_typed_pt(self):
        result = plan_decision(_font_deterministic())
        self.assertEqual(result.status, PlanningStatus.PLANNED)
        op = result.operation
        self.assertEqual(op.precondition_observed, LengthValue(Decimal("11"), "pt"))
        self.assertEqual(op.desired_value, LengthValue(Decimal("12"), "pt"))
        self.assertIsInstance(op.desired_value.value, Decimal)

    # item 60.8 — compare-and-set: precondition comes from decision.observed
    def test_compare_and_set_precondition_preserved(self):
        decision = _font_deterministic()
        op = plan_decision(decision).operation
        self.assertEqual(op.precondition_observed.value, decision.observed)
        self.assertEqual(op.desired_value.value, decision.desired_value)
        self.assertNotEqual(op.precondition_observed, op.desired_value)

    def test_decision_ref_is_canonical_sha256(self):
        decision = _bold_deterministic()
        expected = hashlib.sha256(serialize_decision(decision)).hexdigest()
        self.assertEqual(plan_decision(decision).decision_ref, expected)

    def test_target_copied_field_by_field(self):
        decision = _bold_deterministic()
        op = plan_decision(decision).operation
        target = decision.target
        self.assertEqual(
            (op.target.target_type, op.target.structural_path, op.target.physical_hash,
             op.target.target_class, op.target.aspect_id, op.target.property_slot),
            (target.target_type, target.structural_path, target.physical_hash,
             target.target_class, target.aspect_id, target.property_slot),
        )


class TestSkippedStates(unittest.TestCase):
    # items 60.3–60.6
    def test_no_action_skipped(self):
        result = plan_decision(_spacing_no_action())
        self.assertEqual(result.status, PlanningStatus.SKIPPED)
        self.assertIsNone(result.operation)

    def test_human_choice_skipped(self):
        decision = _decision(
            Actionability.HUMAN_CHOICE, DecisionReason.HUMAN_CHOICE_REQUIRED,
            observed="left", rule_ref=_rule_ref("P4"),
            target=_target("paragraph", "P4", "alignment", path="p[0]"),
        )
        result = plan_decision(decision)
        self.assertEqual(result.status, PlanningStatus.SKIPPED)
        self.assertIsNone(result.operation)

    def test_review_skipped(self):
        result = plan_decision(_alignment_review())
        self.assertEqual(result.status, PlanningStatus.SKIPPED)
        self.assertIsNone(result.operation)

    def test_preserve_rule_absent_skipped_without_rule_ref(self):
        decision = _decision(
            Actionability.PRESERVE, DecisionReason.RULE_ABSENT,
            observed=True, rule_ref=None,
            target=_target("run", "P1", "bold"),
            compliance=ComplianceStatus.NOT_APPLICABLE,
        )
        result = plan_decision(decision)
        self.assertEqual(result.status, PlanningStatus.SKIPPED)
        self.assertIsNone(result.operation)

    def test_preserve_containment_skipped_with_rule_ref(self):
        decision = _decision(
            Actionability.PRESERVE, DecisionReason.CONTAINMENT,
            rule_ref=_rule_ref("P1"),
            target=_target("run", "P1", "bold"),
            compliance=ComplianceStatus.NOT_EVALUATED,
        )
        self.assertEqual(plan_decision(decision).status, PlanningStatus.SKIPPED)


class TestUnsupportedSlot(unittest.TestCase):
    # item 60.7 / 61 — deterministic_change on known-but-unsupported slot
    def test_italic_deterministic_is_unsupported_not_skipped(self):
        decision = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=True, desired=False, rule_ref=_rule_ref("P1"),
            target=_target("run", "P1", "italic"),
        )
        result = plan_decision(decision)
        self.assertEqual(result.status, PlanningStatus.UNSUPPORTED)
        self.assertIsNone(result.operation)


class TestContractErrors(unittest.TestCase):
    # item 60.9 — observed == desired is an upstream contradiction
    def test_observed_equals_desired_fails(self):
        decision = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=True, desired=True, rule_ref=_rule_ref("P1"),
        )
        with self.assertRaises(OperationPlanContractError):
            plan_decision(decision)

    def test_deterministic_without_observed_fails(self):
        decision = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=None, desired=False, rule_ref=_rule_ref("P1"),
        )
        with self.assertRaises(OperationPlanContractError):
            plan_decision(decision)

    # item 60.10 — deterministic_change without rule_ref: never invent authorization
    def test_deterministic_without_rule_ref_fails(self):
        decision = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=True, desired=False, rule_ref=None,
        )
        with self.assertRaises(OperationPlanContractError):
            plan_decision(decision)

    # item 60.11 — key outside the frozen vocabulary is a corrupted Decision
    def test_key_outside_vocabulary_fails(self):
        decision = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=True, desired=False, rule_ref=_rule_ref("P1"),
            target=_target("run", "P1", "underline"),
        )
        with self.assertRaises(OperationPlanContractError):
            plan_decision(decision)

    def test_operation_target_key_binding_enforced(self):
        from formatador_academico.decision import DecisionKey
        from formatador_academico.operation_plan import PlannedOperation
        with self.assertRaises(ValueError):
            PlannedOperation(
                kind=OperationKind.SET_PROPERTY,
                key=DecisionKey("run", "P2", "font_size"),
                target=OperationTarget("run", "p[0]/r[0]", "h" * 16, "body", "P1", "bold"),
                precondition_observed=True,
                desired_value=False,
                decision_ref="b" * 64,
            )

    # item 60.12 — wrong value type per slot
    def test_wrong_value_type_fails(self):
        decision = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed="true", desired=False, rule_ref=_rule_ref("P1"),
        )
        with self.assertRaises(OperationPlanContractError):
            plan_decision(decision)

    def test_wrong_desired_type_fails(self):
        decision = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=Decimal("11"), desired="12", rule_ref=_rule_ref("P2"),
            target=_target("run", "P2", "font_size"),
        )
        with self.assertRaises(OperationPlanContractError):
            plan_decision(decision)

    # item 66 — version compatibility
    def test_wrong_decision_version_fails(self):
        decision = _bold_deterministic()
        object.__setattr__(decision, "decision_version", "0.2")
        with self.assertRaises(OperationPlanContractError):
            plan_decision(decision)

    def test_wrong_vocabulary_version_fails(self):
        decision = _bold_deterministic()
        object.__setattr__(decision, "decision_vocabulary_version", "0.2")
        with self.assertRaises(OperationPlanContractError):
            plan_decision(decision)

    def test_invalid_source_document_ref(self):
        with self.assertRaises(ValueError):
            SourceDocumentRef("not-hex", "0.4.0")
        with self.assertRaises(ValueError):
            SourceDocumentRef("A" * 64, "0.4.0")  # uppercase rejected
        with self.assertRaises(ValueError):
            SourceDocumentRef("a" * 64, "")

    def test_planned_story_part_restricted(self):
        with self.assertRaises(OperationPlanContractError):
            build_operation_plan(SOURCE, UPSTREAM, (), planned_story_part="word/footnotes.xml")


class TestAggregation(unittest.TestCase):
    # item 60.13 — duplicate identical operations fail; never deduplicate
    def test_duplicate_identical_operations_fail(self):
        d1 = _bold_deterministic()
        d2 = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.PREFERRED_VARIANT_DIFFERS,
            observed=True, desired=False, rule_ref=_rule_ref("P1", "r-2"),
            target=_target("run", "P1", "bold"),
        )
        with self.assertRaises(OperationPlanAggregationError):
            build_operation_plan(SOURCE, UPSTREAM, (d1, d2))

    # identical Decision twice fails before producing a valid plan (item 53)
    def test_identical_decision_twice_fails(self):
        d1 = _bold_deterministic()
        with self.assertRaises(OperationPlanAggregationError):
            build_operation_plan(SOURCE, UPSTREAM, (d1, d1))

    # item 60.14 — same target/key with different desired: conflict
    def test_conflicting_desired_fails(self):
        d1 = _font_deterministic()
        d2 = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=Decimal("11"), desired=Decimal("14"), rule_ref=_rule_ref("P2", "r-9"),
            target=_target("run", "P2", "font_size"),
        )
        with self.assertRaises(OperationPlanAggregationError):
            build_operation_plan(SOURCE, UPSTREAM, (d1, d2))

    # item 60.15 — empty plan is valid
    def test_empty_plan_valid(self):
        plan = build_operation_plan(SOURCE, UPSTREAM, ())
        self.assertEqual(plan.operations, ())
        self.assertEqual(plan.planning_results, ())
        self.assertEqual(plan.planned_story_part, PLANNED_STORY_PART)

    def test_all_skipped_plan_has_no_operations(self):
        plan = build_operation_plan(
            SOURCE, UPSTREAM, (_spacing_no_action(), _alignment_review()))
        self.assertEqual(plan.operations, ())
        self.assertEqual(len(plan.planning_results), 2)
        self.assertTrue(all(r.status is PlanningStatus.SKIPPED for r in plan.planning_results))

    # items 42/43 — partial failure: valid operations survive skipped/unsupported
    def test_partial_failure_keeps_valid_operations_and_trail(self):
        italic = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=True, desired=False, rule_ref=_rule_ref("P1", "r-i"),
            target=_target("run", "P1", "italic"),
        )
        decisions = (_bold_deterministic(), _font_deterministic(),
                     _spacing_no_action(), _alignment_review(), italic)
        plan = build_operation_plan(SOURCE, UPSTREAM, decisions)
        self.assertEqual(len(plan.operations), 2)  # mutation budget
        self.assertEqual(len(plan.planning_results), 5)
        statuses = [r.status for r in plan.planning_results]
        self.assertEqual(statuses.count(PlanningStatus.PLANNED), 2)
        self.assertEqual(statuses.count(PlanningStatus.SKIPPED), 2)
        self.assertEqual(statuses.count(PlanningStatus.UNSUPPORTED), 1)

    # items 68/69 — version and profile homogeneity
    def test_profile_heterogeneity_fails(self):
        d1 = _bold_deterministic()
        other_profile = ProfileRef("outro-perfil", "1")
        d2 = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=Decimal("11"), desired=Decimal("12"),
            rule_ref=RuleRef("outro-perfil", "1", "r-2", "P2"),
            target=_target("run", "P2", "font_size"),
        )
        object.__setattr__(d2, "profile_ref", other_profile)
        with self.assertRaises(OperationPlanAggregationError):
            build_operation_plan(SOURCE, UPSTREAM, (d1, d2))

    def test_upstream_version_mismatch_fails(self):
        wrong = UpstreamVersions("0.1b-m2", "0.1", "0.2", "0.1")
        with self.assertRaises(OperationPlanAggregationError):
            build_operation_plan(SOURCE, wrong, (_bold_deterministic(),))

    # item 60.16 — total deterministic operation ordering
    def test_operation_ordering_deterministic(self):
        decisions = (_bold_deterministic(), _font_deterministic())
        plan1 = build_operation_plan(SOURCE, UPSTREAM, decisions)
        plan2 = build_operation_plan(SOURCE, UPSTREAM, tuple(reversed(decisions)))
        self.assertEqual(plan1.operations, plan2.operations)
        paths = [(op.target.aspect_id, op.target.property_slot) for op in plan1.operations]
        self.assertEqual(paths, [("P1", "bold"), ("P2", "font_size")])

    # item 60.17 — source_decisions_hash is order-independent
    def test_source_decisions_hash_order_independent(self):
        decisions = (_bold_deterministic(), _font_deterministic(),
                     _spacing_no_action(), _alignment_review())
        plan1 = build_operation_plan(SOURCE, UPSTREAM, decisions)
        plan2 = build_operation_plan(SOURCE, UPSTREAM, tuple(reversed(decisions)))
        self.assertEqual(plan1.source_decisions_hash, plan2.source_decisions_hash)

    # item 60.18 — changing a Decision changes the hash
    def test_source_decisions_hash_changes_with_decision(self):
        decisions = (_bold_deterministic(), _font_deterministic())
        plan1 = build_operation_plan(SOURCE, UPSTREAM, decisions)
        changed = _decision(
            Actionability.DETERMINISTIC_CHANGE, DecisionReason.DIFFERS_FROM_RULE,
            observed=Decimal("10"), desired=Decimal("12"), rule_ref=_rule_ref("P2"),
            target=_target("run", "P2", "font_size"),
        )
        plan2 = build_operation_plan(SOURCE, UPSTREAM, (decisions[0], changed))
        self.assertNotEqual(plan1.source_decisions_hash, plan2.source_decisions_hash)


class TestSerializationDeterminism(unittest.TestCase):
    def _plan(self):
        decisions = (_bold_deterministic(), _font_deterministic(),
                     _spacing_no_action(), _alignment_review())
        return build_operation_plan(SOURCE, UPSTREAM, decisions)

    # item 60.20 — deterministic serialization, same process
    def test_serialization_deterministic_same_process(self):
        self.assertEqual(serialize_operation_plan(self._plan()),
                         serialize_operation_plan(self._plan()))

    # item 60.21 — cross-process / hashseed determinism
    def test_serialization_deterministic_across_hashseeds(self):
        script = (
            "from decimal import Decimal;"
            "from test_operation_plan_v01 import SOURCE, UPSTREAM, _bold_deterministic,"
            "_font_deterministic, _spacing_no_action, _alignment_review;"
            "from formatador_academico.operation_plan import "
            "build_operation_plan, serialize_operation_plan;"
            "import hashlib, sys;"
            "plan = build_operation_plan(SOURCE, UPSTREAM, (_bold_deterministic(),"
            "_font_deterministic(), _spacing_no_action(), _alignment_review()));"
            "sys.stdout.write(hashlib.sha256(serialize_operation_plan(plan)).hexdigest())"
        )
        root = Path(__file__).resolve().parent.parent
        env_base = dict(os.environ)
        env_base["PYTHONPATH"] = f"{root / 'src'}{os.pathsep}{root / 'tests'}"
        digests = set()
        for seed in ("0", "42", "7", "123"):
            env = dict(env_base, PYTHONHASHSEED=seed)
            out = subprocess.run(
                [sys.executable, "-c", script],
                check=True, capture_output=True, text=True, env=env, cwd=root,
            )
            digests.add(out.stdout.strip())
        self.assertEqual(len(digests), 1)

    # item 60.22 — immutability
    def test_models_frozen(self):
        plan = self._plan()
        with self.assertRaises(FrozenInstanceError):
            plan.operations = ()
        with self.assertRaises(FrozenInstanceError):
            plan.operations[0].desired_value = True
        with self.assertRaises(FrozenInstanceError):
            plan.source_document.package_sha256 = "b" * 64
        self.assertIsInstance(plan.operations, tuple)
        self.assertIsInstance(plan.planning_results, tuple)

    # inputs are not mutated by planning
    def test_inputs_not_mutated(self):
        decision = _bold_deterministic()
        snapshot = copy.deepcopy(decision)
        plan_decision(decision)
        build_operation_plan(SOURCE, UPSTREAM, (decision,))
        self.assertEqual(serialize_decision(decision), serialize_decision(snapshot))

    def test_versions_in_envelope(self):
        plan = self._plan()
        self.assertEqual(plan.operation_plan_version, OPERATION_PLAN_VERSION)
        self.assertEqual(plan.operation_vocabulary_version, OPERATION_VOCABULARY_VERSION)
        self.assertEqual(plan.upstream_versions.decision_version, "0.1")
        self.assertEqual(plan.source_document.parser_version, "0.4.0")


if __name__ == "__main__":
    unittest.main()
