"""SafetyGate v0.1 — unit tests.

Covers the minimum scenarios of decision 0026 / technical briefing: global
vetoes, local vetoes, integrity/binding errors, refs determinism,
serialization determinism, immutability and non-mutation.

Local drift tests use controlled unit contexts (docs/briefing item 80): the
plan is built from Decisions whose declared observed values differ from the
current document, so the global package check stays intact and the intended
local veto is what fires.
"""

from __future__ import annotations

import copy
import hashlib
import os
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

from formatador_academico.analysis.formatting_model import ANALYSIS_FORMATTING_VERSION
from formatador_academico.analysis.style_catalog import build_style_catalog
from formatador_academico.classification import CLASSIFICATION_VERSION
from formatador_academico.decision import (
    DECISION_VERSION,
    DECISION_VOCABULARY_VERSION,
    Actionability,
    ComplianceStatus,
    Decision,
    DecisionReason,
    DecisionTarget,
    ProfileRef,
    RuleRef,
    serialize_decision,
)
from formatador_academico.docx_parser import DocxParser
from formatador_academico.operation_plan import (
    LengthValue,
    SourceDocumentRef,
    UpstreamVersions,
    build_operation_plan,
    decision_ref,
    operation_plan_ref,
    operation_ref,
    serialize_operation_plan,
    source_decisions_hash,
    source_document_ref_from_physical_ir,
)
from formatador_academico.safety_gate import (
    SAFETY_GATE_VERSION,
    ContextStatus,
    GateClearedOperation,
    GateReason,
    GateResult,
    GateStatus,
    SafetyGateContractError,
    SafetyGateIntegrityError,
    evaluate_operation_plan,
    gate_operation,
    serialize_safety_gate_report,
)
from formatador_academico.safety_gate.targets import (
    index_story_targets,
    resolve_target,
    walk_records,
)

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL

PROFILE = ProfileRef("perfil-teste", "1")

BODY = (
    '<w:p><w:pPr><w:jc w:val="both"/>'
    '<w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
    '<w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr>'
    "<w:t>corpo</w:t></w:r></w:p>"
)


def _parse(body=BODY):
    pkg = build_docx(document(body), styles_part(NORMAL))
    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    catalog = build_style_catalog(pkg, ir)
    paragraph = ir["stories"][0]["blocks"][0]
    run = next((c for c in paragraph["children"] if c["source_type"] == "run_raw"), None)
    return pkg, ir, catalog, paragraph, run


def _decision(record, key_slot, observed, desired, *, aspect, target_type="run",
              profile=PROFILE, actionability=Actionability.DETERMINISTIC_CHANGE,
              rule_ref=None, reason=DecisionReason.DIFFERS_FROM_RULE):
    if rule_ref is None and actionability is Actionability.DETERMINISTIC_CHANGE:
        rule_ref = RuleRef(profile.profile_id, profile.profile_version,
                           f"rule-{key_slot}", aspect)
    return Decision(
        decision_version=DECISION_VERSION,
        decision_vocabulary_version=DECISION_VOCABULARY_VERSION,
        target=DecisionTarget(
            target_type=target_type,
            structural_path=record["structural_path"],
            physical_hash=record["physical_hash"],
            target_class="body_text",
            aspect_id=aspect,
            property_slot=key_slot,
        ),
        compliance=ComplianceStatus.NON_COMPLIANT,
        actionability=actionability,
        reason=reason,
        analysis_status="resolved",
        observed=observed,
        desired_value=desired,
        profile_ref=profile,
        rule_ref=rule_ref,
        evidence_ref=None,
    )


def _upstream(**overrides):
    values = dict(
        analysis_formatting_version=ANALYSIS_FORMATTING_VERSION,
        classification_version=CLASSIFICATION_VERSION,
        decision_version=DECISION_VERSION,
        decision_vocabulary_version=DECISION_VOCABULARY_VERSION,
    )
    values.update(overrides)
    return UpstreamVersions(**values)


def _plan_for(ir, decisions, upstream=None):
    return build_operation_plan(
        source_document_ref_from_physical_ir(ir), upstream or _upstream(), decisions
    )


def _bold_font_plan(ir, run, *, bold_observed=True, font_observed=Decimal("11")):
    d_bold = _decision(run, "bold", bold_observed, False, aspect="P1")
    d_font = _decision(run, "font_size", font_observed, Decimal("12"), aspect="P2")
    decisions = (d_bold, d_font)
    return decisions, _plan_for(ir, decisions)


def _evaluate(plan, decisions, ir, catalog, profile=PROFILE):
    return evaluate_operation_plan(plan, decisions, ir, catalog, profile)


class TestPublicHelpers(unittest.TestCase):
    """Regression: additive public helpers delegate to the frozen canonical logic."""

    @classmethod
    def setUpClass(cls):
        _, cls.ir, cls.catalog, _, cls.run_rec = _parse()
        cls.decisions, cls.plan = _bold_font_plan(cls.ir, cls.run_rec)

    def test_decision_ref_matches_frozen_hash(self):
        for d in self.decisions:
            self.assertEqual(decision_ref(d), hashlib.sha256(serialize_decision(d)).hexdigest())
        for op in self.plan.operations:
            self.assertEqual(op.decision_ref, decision_ref(
                next(d for d in self.decisions
                     if hashlib.sha256(serialize_decision(d)).hexdigest() == op.decision_ref)))

    def test_source_decisions_hash_matches_plan(self):
        self.assertEqual(source_decisions_hash(self.decisions), self.plan.source_decisions_hash)
        self.assertEqual(source_decisions_hash(tuple(reversed(self.decisions))),
                         self.plan.source_decisions_hash)

    def test_operation_plan_ref(self):
        self.assertEqual(operation_plan_ref(self.plan),
                         hashlib.sha256(serialize_operation_plan(self.plan)).hexdigest())
        altered = replace(self.plan, planned_story_part=self.plan.planned_story_part,
                          source_decisions_hash="0" * 64)
        self.assertNotEqual(operation_plan_ref(altered), operation_plan_ref(self.plan))

    def test_operation_ref_deterministic_and_sensitive(self):
        (op,) = [o for o in self.plan.operations if o.key.property_slot == "font_size"]
        self.assertEqual(operation_ref(op), operation_ref(op))
        self.assertNotEqual(
            operation_ref(replace(op, desired_value=LengthValue(Decimal("14"), "pt"))),
            operation_ref(op))
        self.assertNotEqual(
            operation_ref(replace(op, precondition_observed=LengthValue(Decimal("10"), "pt"))),
            operation_ref(op))
        other_target = replace(op.target, physical_hash="a" * 64)
        self.assertNotEqual(
            operation_ref(replace(op, target=other_target)), operation_ref(op))


class TestUnchangedCleared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ir, cls.catalog, _, cls.run_rec = _parse()
        cls.decisions, cls.plan = _bold_font_plan(cls.ir, cls.run_rec)
        cls.report = _evaluate(cls.plan, cls.decisions, cls.ir, cls.catalog)

    def test_context_compatible(self):
        self.assertEqual(self.report.context_status, ContextStatus.COMPATIBLE)
        self.assertEqual(self.report.context_reasons, ())
        self.assertEqual(self.report.safety_gate_version, SAFETY_GATE_VERSION)

    def test_bold_cleared(self):
        (op,) = [o for o in self.plan.operations if o.key.property_slot == "bold"]
        (result,) = [r for r in self.report.results
                     if r.operation_ref == operation_ref(op)]
        self.assertEqual(result.status, GateStatus.CLEARED)
        self.assertEqual(result.reasons, ())
        self.assertIs(result.evidence.current_observed, True)

    def test_font_cleared(self):
        (op,) = [o for o in self.plan.operations if o.key.property_slot == "font_size"]
        (result,) = [r for r in self.report.results
                     if r.operation_ref == operation_ref(op)]
        self.assertEqual(result.status, GateStatus.CLEARED)
        self.assertEqual(result.evidence.current_observed, LengthValue(Decimal("11"), "pt"))

    def test_cleared_operations_tokens(self):
        self.assertEqual(len(self.report.cleared_operations), 2)
        plan_ref = operation_plan_ref(self.plan)
        for token in self.report.cleared_operations:
            self.assertEqual(token.operation_plan_ref, plan_ref)
            self.assertEqual(token.current_package_sha256,
                             self.ir["package"]["sha256"])
            self.assertEqual(token.current_package_sha256,
                             self.report.current_package_sha256)
        # identity: the embedded operation is the same immutable object
        by_ref = {operation_ref(o): o for o in self.plan.operations}
        for token in self.report.cleared_operations:
            self.assertIs(token.operation, by_ref[token.operation_ref])

    def test_results_follow_plan_order(self):
        self.assertEqual(
            tuple(r.operation_ref for r in self.report.results),
            tuple(operation_ref(o) for o in self.plan.operations),
        )

    def test_cleared_token_not_publicly_constructible(self):
        (op,) = self.plan.operations[:1]
        with self.assertRaises(SafetyGateContractError):
            GateClearedOperation(
                operation=op,
                operation_ref=operation_ref(op),
                operation_plan_ref=operation_plan_ref(self.plan),
                current_package_sha256=self.ir["package"]["sha256"],
            )


class TestGlobalVetoes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg, cls.ir, cls.catalog, _, cls.run_rec = _parse()
        cls.decisions, cls.plan = _bold_font_plan(cls.ir, cls.run_rec)

    def _assert_global(self, report, reason):
        self.assertEqual(report.context_status, ContextStatus.BLOCKED)
        self.assertEqual(report.context_reasons, (reason,))
        self.assertEqual(len(report.results), len(self.plan.operations))
        self.assertTrue(all(r.status is GateStatus.BLOCKED for r in report.results))
        self.assertTrue(all(r.reasons == (reason,) for r in report.results))
        self.assertEqual(report.cleared_operations, ())

    def test_package_mismatch_global(self):
        # Real re-parse of a modified package (stale document).
        pkg_b = build_docx(document(BODY.replace("corpo", "alterado")),
                           styles_part(NORMAL))
        ir_b = DocxParser().parse_bytes(pkg_b)
        catalog_b = build_style_catalog(pkg_b, ir_b)
        report = _evaluate(self.plan, self.decisions, ir_b, catalog_b)
        self._assert_global(report, GateReason.SOURCE_DOCUMENT_CHANGED)
        ev = report.results[0].evidence
        self.assertEqual(ev.expected, self.plan.source_document.package_sha256)
        self.assertEqual(ev.actual, ir_b["package"]["sha256"])

    def test_parser_version_mismatch_global(self):
        plan = replace(self.plan, source_document=SourceDocumentRef(
            package_sha256=self.plan.source_document.package_sha256,
            parser_version="0.0-unittest"))
        report = _evaluate(plan, self.decisions, self.ir, self.catalog)
        self._assert_global(report, GateReason.PARSER_VERSION_MISMATCH)
        self.assertEqual(report.results[0].evidence.actual, self.ir["parser_version"])

    def test_analysis_version_mismatch_global(self):
        plan = replace(self.plan, upstream_versions=_upstream(
            analysis_formatting_version="0.0-unittest"))
        report = _evaluate(plan, self.decisions, self.ir, self.catalog)
        self._assert_global(report, GateReason.ANALYSIS_VERSION_MISMATCH)
        self.assertEqual(report.results[0].evidence.actual, ANALYSIS_FORMATTING_VERSION)

    def test_classification_version_mismatch_global(self):
        plan = replace(self.plan, upstream_versions=_upstream(
            classification_version="0.0-unittest"))
        report = _evaluate(plan, self.decisions, self.ir, self.catalog)
        self._assert_global(report, GateReason.CLASSIFICATION_VERSION_MISMATCH)
        self.assertEqual(report.results[0].evidence.actual, CLASSIFICATION_VERSION)

    def test_profile_mismatch_global(self):
        report = _evaluate(self.plan, self.decisions, self.ir, self.catalog,
                           profile=ProfileRef("perfil-teste", "2"))
        self._assert_global(report, GateReason.PROFILE_CONTEXT_CHANGED)
        ev = report.results[0].evidence
        self.assertEqual(ev.expected, PROFILE)
        self.assertEqual(ev.actual, ProfileRef("perfil-teste", "2"))

    def test_profile_id_mismatch_global(self):
        report = _evaluate(self.plan, self.decisions, self.ir, self.catalog,
                           profile=ProfileRef("outro-perfil", "1"))
        self._assert_global(report, GateReason.PROFILE_CONTEXT_CHANGED)


class TestLocalVetoes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ir, cls.catalog, cls.paragraph, cls.run_rec = _parse()

    def _gate_single(self, decision):
        plan = _plan_for(self.ir, (decision,))
        (op,) = plan.operations
        return gate_operation(op, decision, self.ir, self.catalog)

    def test_target_not_found(self):
        decision = _decision(
            {**self.run_rec, "structural_path": "/w:document/w:body[1]/w:p[9]/w:r[1]"},
            "bold", True, False, aspect="P1")
        result = self._gate_single(decision)
        self.assertEqual(result.status, GateStatus.BLOCKED)
        self.assertEqual(result.reasons, (GateReason.TARGET_NOT_FOUND,))

    def test_story_target_index_preserves_path_resolution(self):
        story = self.ir["stories"][0]
        indexed = index_story_targets(story)
        paths = {record["structural_path"] for record, _ in walk_records(story["blocks"])}
        self.assertEqual(set(indexed), paths)
        for path in paths:
            expected = resolve_target(story, path)
            actual = indexed[path]
            self.assertEqual(len(actual), len(expected))
            for (actual_record, actual_ancestors), (expected_record, expected_ancestors) in zip(
                actual, expected
            ):
                self.assertIs(actual_record, expected_record)
                self.assertEqual(actual_ancestors, expected_ancestors)

        missing = "/w:document/w:body[1]/w:p[999]"
        self.assertEqual(indexed.get(missing, []), resolve_target(story, missing))

    def test_story_target_index_preserves_duplicates_and_empty_story(self):
        story = copy.deepcopy(self.ir["stories"][0])
        story["blocks"].append(copy.deepcopy(story["blocks"][0]))
        path = self.run_rec["structural_path"]
        indexed = index_story_targets(story)
        resolved = resolve_target(story, path)
        self.assertEqual(len(indexed[path]), 2)
        self.assertEqual(len(resolved), 2)
        for (actual_record, actual_ancestors), (expected_record, expected_ancestors) in zip(
            indexed[path], resolved
        ):
            self.assertIs(actual_record, expected_record)
            self.assertEqual(actual_ancestors, expected_ancestors)

        empty_story = {"blocks": []}
        self.assertEqual(index_story_targets(empty_story), {})
        with self.assertRaises(SafetyGateContractError):
            index_story_targets({"blocks": None})

    def test_empty_plan_does_not_index_invalid_story(self):
        plan = _plan_for(self.ir, ())
        invalid_ir = copy.deepcopy(self.ir)
        invalid_ir["stories"][0]["blocks"] = None
        report = _evaluate(plan, (), invalid_ir, self.catalog)
        self.assertEqual(report.context_status, ContextStatus.COMPATIBLE)
        self.assertEqual(report.results, ())

    def test_target_not_unique(self):
        decision = _decision(self.run_rec, "bold", True, False, aspect="P1")
        plan = _plan_for(self.ir, (decision,))
        (op,) = plan.operations
        adulterated = copy.deepcopy(self.ir)
        adulterated["stories"][0]["blocks"].append(
            copy.deepcopy(adulterated["stories"][0]["blocks"][0]))
        result = gate_operation(op, decision, adulterated, self.catalog)
        self.assertEqual(result.reasons, (GateReason.TARGET_NOT_UNIQUE,))
        self.assertEqual(result.evidence.actual, 2)

    def test_target_type_mismatch(self):
        # target_type run pointing at the paragraph record.
        decision = _decision(self.paragraph, "bold", True, False, aspect="P1")
        result = self._gate_single(decision)
        self.assertEqual(result.reasons, (GateReason.TARGET_TYPE_MISMATCH,))
        self.assertEqual(result.evidence.actual, "paragraph")

    def test_physical_hash_mismatch(self):
        tampered_hash = ("0" if self.run_rec["physical_hash"][0] != "0" else "1") + \
            self.run_rec["physical_hash"][1:]
        decision = _decision({**self.run_rec, "physical_hash": tampered_hash},
                             "bold", True, False, aspect="P1")
        result = self._gate_single(decision)
        self.assertEqual(result.reasons, (GateReason.PHYSICAL_HASH_MISMATCH,))
        self.assertEqual(result.evidence.expected, tampered_hash)
        self.assertEqual(result.evidence.actual, self.run_rec["physical_hash"])

    def test_current_value_unavailable(self):
        # run without w:b and Normal style without bold -> bold absent.
        body = ('<w:p><w:r><w:rPr><w:sz w:val="22"/></w:rPr>'
                "<w:t>sem negrito</w:t></w:r></w:p>")
        _, ir, catalog, _, run = _parse(body)
        decision = _decision(run, "bold", False, True, aspect="P1")
        plan = _plan_for(ir, (decision,))
        (op,) = plan.operations
        result = gate_operation(op, decision, ir, catalog)
        self.assertEqual(result.reasons, (GateReason.CURRENT_VALUE_UNAVAILABLE,))
        self.assertEqual(result.evidence.actual, "analysis_status:absent")

    def test_precondition_mismatch_third_value(self):
        # planned 13 -> 12, current 11: precondition_mismatch; gate never re-plans.
        decision = _decision(self.run_rec, "font_size", Decimal("13"), Decimal("12"),
                             aspect="P2")
        result = self._gate_single(decision)
        self.assertEqual(result.reasons, (GateReason.PRECONDITION_MISMATCH,))
        self.assertEqual(result.evidence.expected, LengthValue(Decimal("13"), "pt"))
        self.assertEqual(result.evidence.actual, LengthValue(Decimal("11"), "pt"))

    def test_current_equals_desired_is_still_stale(self):
        # planned 11 -> 12, current 12: precondition_mismatch, never no_action.
        body = ('<w:p><w:r><w:rPr><w:sz w:val="24"/></w:rPr>'
                "<w:t>doze</w:t></w:r></w:p>")
        _, ir, catalog, _, run = _parse(body)
        decision = _decision(run, "font_size", Decimal("11"), Decimal("12"),
                             aspect="P2")
        plan = _plan_for(ir, (decision,))
        (op,) = plan.operations
        result = gate_operation(op, decision, ir, catalog)
        self.assertEqual(result.reasons, (GateReason.PRECONDITION_MISMATCH,))
        self.assertEqual(result.evidence.actual, LengthValue(Decimal("12"), "pt"))

    def test_run_container_paragraph_ancestor(self):
        # paragraph -> hyperlink (run_container) -> run: the real paragraph
        # ancestor must be found through tree ancestry.
        body = ('<w:p><w:hyperlink><w:r><w:rPr><w:b/></w:rPr>'
                "<w:t>link</w:t></w:r></w:hyperlink></w:p>")
        _, ir, catalog, paragraph, _ = _parse(body)
        container = next(c for c in paragraph["children"]
                         if c["source_type"] == "run_container")
        run = next(c for c in container["children"] if c["source_type"] == "run_raw")
        self.assertIn("hyperlink", run["structural_path"])
        decision = _decision(run, "bold", True, False, aspect="P1")
        plan = _plan_for(ir, (decision,))
        report = _evaluate(plan, (decision,), ir, catalog)
        self.assertEqual(report.context_status, ContextStatus.COMPATIBLE)
        self.assertEqual(report.results[0].status, GateStatus.CLEARED)
        self.assertIs(report.results[0].evidence.current_observed, True)

    def test_partial_clearance(self):
        d_bold = _decision(self.run_rec, "bold", True, False, aspect="P1")
        tampered = ("0" if self.run_rec["physical_hash"][0] != "0" else "1") + \
            self.run_rec["physical_hash"][1:]
        d_font = _decision({**self.run_rec, "physical_hash": tampered},
                           "font_size", Decimal("11"), Decimal("12"), aspect="P2")
        decisions = (d_bold, d_font)
        plan = _plan_for(self.ir, decisions)
        report = _evaluate(plan, decisions, self.ir, self.catalog)
        self.assertEqual(report.context_status, ContextStatus.COMPATIBLE)
        statuses = {r.status for r in report.results}
        self.assertEqual(statuses, {GateStatus.CLEARED, GateStatus.BLOCKED})
        self.assertEqual(len(report.cleared_operations), 1)
        (blocked,) = [r for r in report.results if r.status is GateStatus.BLOCKED]
        self.assertEqual(blocked.reasons, (GateReason.PHYSICAL_HASH_MISMATCH,))

    def test_empty_plan(self):
        plan = _plan_for(self.ir, ())
        self.assertEqual(plan.operations, ())
        report = _evaluate(plan, (), self.ir, self.catalog)
        self.assertEqual(report.context_status, ContextStatus.COMPATIBLE)
        self.assertEqual(report.results, ())
        self.assertEqual(report.cleared_operations, ())
        # serialization is still valid/deterministic
        self.assertEqual(serialize_safety_gate_report(report),
                         serialize_safety_gate_report(report))


def _replace_operation(plan, ref_op, altered_op):
    """Artificially tamper with a planned operation, keeping the frozen plan
    envelope invariant (operations == planned operations of the trail)."""

    operations = tuple(altered_op if o is ref_op else o for o in plan.operations)
    trail = tuple(
        replace(r, operation=altered_op) if r.operation is ref_op else r
        for r in plan.planning_results
    )
    return replace(plan, operations=operations, planning_results=trail)


class TestIntegrityErrors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ir, cls.catalog, _, cls.run_rec = _parse()
        cls.decisions, cls.plan = _bold_font_plan(cls.ir, cls.run_rec)

    def test_source_decisions_hash_mismatch(self):
        other = _decision(self.run_rec, "bold", True, False, aspect="P1",
                          profile=ProfileRef("perfil-b", "1"))
        with self.assertRaises(SafetyGateIntegrityError):
            _evaluate(self.plan, (other,), self.ir, self.catalog)

    def test_duplicate_source_decision(self):
        with self.assertRaises(SafetyGateIntegrityError):
            _evaluate(self.plan, (self.decisions[0], self.decisions[0]),
                      self.ir, self.catalog)

    def test_missing_source_decision(self):
        with self.assertRaises(SafetyGateIntegrityError):
            _evaluate(self.plan, self.decisions[:1], self.ir, self.catalog)

    def test_operation_decision_target_mismatch(self):
        # plan copied artificially with an altered operation target
        (op,) = [o for o in self.plan.operations if o.key.property_slot == "bold"]
        altered_op = replace(op, target=replace(op.target, target_class="heading"))
        plan = _replace_operation(self.plan, op, altered_op)
        with self.assertRaises(SafetyGateIntegrityError):
            _evaluate(plan, self.decisions, self.ir, self.catalog)

    def test_altered_desired_binding(self):
        (op,) = [o for o in self.plan.operations if o.key.property_slot == "font_size"]
        altered_op = replace(op, desired_value=LengthValue(Decimal("14"), "pt"))
        plan = _replace_operation(self.plan, op, altered_op)
        with self.assertRaises(SafetyGateIntegrityError):
            _evaluate(plan, self.decisions, self.ir, self.catalog)

    def test_altered_precondition_binding(self):
        (op,) = [o for o in self.plan.operations if o.key.property_slot == "font_size"]
        altered_op = replace(op, precondition_observed=LengthValue(Decimal("10"), "pt"))
        plan = _replace_operation(self.plan, op, altered_op)
        with self.assertRaises(SafetyGateIntegrityError):
            _evaluate(plan, self.decisions, self.ir, self.catalog)

    def test_altered_decision_breaks_ref_resolution(self):
        # any semantic change to a source Decision changes its ref; the plan's
        # decision_ref then resolves to nothing -> integrity error.
        altered = replace(self.decisions[0],
                          actionability=Actionability.REVIEW, desired_value=None)
        with self.assertRaises(SafetyGateIntegrityError):
            _evaluate(self.plan, (altered,) + self.decisions[1:],
                      self.ir, self.catalog)

    def test_style_catalog_ab_binding(self):
        # StyleCatalog built from package B must not gate against PhysicalIR A.
        pkg_b = build_docx(document(BODY), styles_part(NORMAL + (
            '<w:style w:type="character" w:styleId="X"><w:name w:val="x"/></w:style>')))
        ir_b = DocxParser().parse_bytes(pkg_b)
        catalog_b = build_style_catalog(pkg_b, ir_b)
        # package bytes differ -> package veto would mask binding at plan level;
        # use the same document bytes scenario: alter only styles part so the
        # catalog genuinely belongs to another package.
        with self.assertRaises(SafetyGateIntegrityError):
            _evaluate(self.plan, self.decisions, self.ir, catalog_b)


class TestContractErrors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ir, cls.catalog, _, cls.run_rec = _parse()
        cls.decisions, cls.plan = _bold_font_plan(cls.ir, cls.run_rec)

    def test_api_types(self):
        with self.assertRaises(SafetyGateContractError):
            evaluate_operation_plan("not-a-plan", self.decisions, self.ir,
                                    self.catalog, PROFILE)
        with self.assertRaises(SafetyGateContractError):
            evaluate_operation_plan(self.plan, list(self.decisions), self.ir,
                                    self.catalog, PROFILE)
        with self.assertRaises(SafetyGateContractError):
            evaluate_operation_plan(self.plan, self.decisions, None,
                                    self.catalog, PROFILE)
        with self.assertRaises(SafetyGateContractError):
            evaluate_operation_plan(self.plan, self.decisions, self.ir,
                                    "not-a-catalog", PROFILE)
        with self.assertRaises(SafetyGateContractError):
            evaluate_operation_plan(self.plan, self.decisions, self.ir,
                                    self.catalog, ("p", "1"))

    def test_gate_operation_ref_mismatch(self):
        (op,) = self.plan.operations[:1]
        other = _decision(self.run_rec, "bold", True, False, aspect="P1",
                          profile=ProfileRef("perfil-c", "1"))
        with self.assertRaises(SafetyGateIntegrityError):
            gate_operation(op, other, self.ir, self.catalog)


class TestDeterminismAndImmutability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ir, cls.catalog, _, cls.run_rec = _parse()
        cls.decisions, cls.plan = _bold_font_plan(cls.ir, cls.run_rec)

    def test_serialization_deterministic(self):
        report = _evaluate(self.plan, self.decisions, self.ir, self.catalog)
        self.assertEqual(serialize_safety_gate_report(report),
                         serialize_safety_gate_report(report))

    def test_source_decisions_order_independence(self):
        forward = _evaluate(self.plan, self.decisions, self.ir, self.catalog)
        backward = _evaluate(self.plan, tuple(reversed(self.decisions)),
                             self.ir, self.catalog)
        self.assertEqual(serialize_safety_gate_report(forward),
                         serialize_safety_gate_report(backward))

    def test_hashseed_determinism(self):
        code = (
            "import sys; sys.path.insert(0, 'tests'); sys.path.insert(0, 'src');"
            "from test_safety_gate_v01 import _parse, _bold_font_plan, _evaluate;"
            "from formatador_academico.safety_gate import serialize_safety_gate_report;"
            "_, ir, catalog, _, run = _parse();"
            "decisions, plan = _bold_font_plan(ir, run);"
            "report = _evaluate(plan, decisions, ir, catalog);"
            "sys.stdout.buffer.write(serialize_safety_gate_report(report))"
        )
        outputs = []
        for seed in ("0", "42", "7", "123"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            proc = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, env=env,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                check=True)
            outputs.append(proc.stdout)
        self.assertTrue(all(o == outputs[0] for o in outputs))
        self.assertTrue(outputs[0])

    def test_models_frozen(self):
        report = _evaluate(self.plan, self.decisions, self.ir, self.catalog)
        for model in (report, report.results[0], report.results[0].evidence,
                      report.cleared_operations[0]):
            with self.assertRaises(FrozenInstanceError):
                setattr(model, "_frozen_probe", 1)
        with self.assertRaises(FrozenInstanceError):
            report.results[0].status = GateStatus.BLOCKED

    def test_inputs_not_mutated(self):
        plan_bytes = serialize_operation_plan(self.plan)
        decision_bytes = tuple(serialize_decision(d) for d in self.decisions)
        ir_snapshot = copy.deepcopy(self.ir)
        _evaluate(self.plan, self.decisions, self.ir, self.catalog)
        self.assertEqual(serialize_operation_plan(self.plan), plan_bytes)
        self.assertEqual(tuple(serialize_decision(d) for d in self.decisions),
                         decision_bytes)
        self.assertEqual(self.ir, ir_snapshot)

    def test_status_vocabulary_closed(self):
        self.assertEqual({s.value for s in GateStatus}, {"cleared", "blocked"})
        self.assertEqual({s.value for s in ContextStatus}, {"compatible", "blocked"})
        self.assertEqual(
            {r.value for r in GateReason},
            {
                "source_document_changed", "parser_version_mismatch",
                "analysis_version_mismatch", "classification_version_mismatch",
                "profile_context_changed", "target_not_found",
                "target_not_unique", "target_type_mismatch",
                "physical_hash_mismatch", "current_value_unavailable",
                "precondition_mismatch",
            },
        )

    def test_blocked_result_single_reason_invariant(self):
        with self.assertRaises(ValueError):
            GateResult(operation_ref="a" * 64, status=GateStatus.BLOCKED,
                       reasons=(), evidence=None)
        with self.assertRaises(ValueError):
            GateResult(operation_ref="a" * 64, status=GateStatus.CLEARED,
                       reasons=(GateReason.TARGET_NOT_FOUND,), evidence=None)


if __name__ == "__main__":
    unittest.main()
