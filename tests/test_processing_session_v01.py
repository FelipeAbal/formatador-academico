"""Processing Session / Orchestration v0.1 tests (decision 0032)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch as mock_patch

from formatador_academico.analysis.formatting import resolve_paragraph_formatting, resolve_run_formatting
from formatador_academico.analysis.style_catalog import build_style_catalog
from formatador_academico.classification import ClassificationStatus, classify_document
from formatador_academico.decision import (
    Actionability,
    FormattingRule,
    LineSpacingValue,
    ProfileRef,
    RuleMode,
)
from formatador_academico.docx_parser import DocxParser
from formatador_academico.patcher import (
    PATCHER_VERSION,
    PatchReason,
    PatchResult,
    PatchStatus,
    apply_cleared_operation as real_apply_cleared_operation,
)
from formatador_academico.processing_session import (
    PROCESSING_SESSION_VERSION,
    ProcessingProfile,
    ProcessingSessionContractError,
    ProcessingSessionIntegrityError,
    ProcessingSessionStatus,
    RuleBinding,
    SessionFindingKind,
    process_document,
)
from formatador_academico.safety_gate import (
    ContextStatus,
    GateReason,
    GateResult,
    GateStatus,
    SafetyGateReport,
    evaluate_operation_plan as real_evaluate_operation_plan,
)
from formatador_academico.transform_log import transform_ref

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import HEADING1, NORMAL

PROFILE_REF = ProfileRef("session-profile", "1")


def _bold_rule(expected=False, rule_id="body-bold"):
    return FormattingRule(rule_id, "P1", "bold", RuleMode.EXACT, expected=expected)


def _font_rule(expected=Decimal("12"), rule_id="body-font"):
    return FormattingRule(rule_id, "P2", "font_size", RuleMode.EXACT, expected=expected)


def _profile(*bindings):
    return ProcessingProfile(PROFILE_REF, tuple(bindings))


def _body_profile(*, bold=False, font=Decimal("12"), order="bold-font"):
    b = RuleBinding("body", "run", _bold_rule(bold))
    f = RuleBinding("body", "run", _font_rule(font))
    return _profile(*(b, f) if order == "bold-font" else (f, b))


def _run(text, *, bold=True, half_points=22):
    bold_xml = "<w:b/>" if bold else '<w:b w:val="0"/>'
    return (
        "<w:r><w:rPr>"
        + bold_xml
        + f'<w:sz w:val="{half_points}"/>'
        + f"</w:rPr><w:t>{text}</w:t></w:r>"
    )


def _paragraph(*runs, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return "<w:p>" + ppr + "".join(runs) + "</w:p>"


def _pkg(body, *, styles=NORMAL):
    return build_docx(document(body), styles_part(styles))


def _iter_paragraphs(records):
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("source_type") == "paragraph":
            yield record
            continue
        children = record.get("children")
        if isinstance(children, list):
            yield from _iter_paragraphs(children)


def _iter_runs(record):
    children = record.get("children")
    if not isinstance(children, list):
        return
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("source_type") == "run_raw":
            yield child
            continue
        yield from _iter_runs(child)


def _body_run_states(pkg):
    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    catalog = build_style_catalog(pkg, ir)
    story = ir["stories"][0]
    states = []
    for paragraph in _iter_paragraphs(story["blocks"]):
        for run in _iter_runs(paragraph):
            rf = resolve_run_formatting(run, paragraph, catalog, story["part"])
            states.append((run["structural_path"], rf.bold, rf.font_size))
    return states


def _two_change_pkg():
    return _pkg(_paragraph(_run("one", bold=True, half_points=22)))


class ProcessingProfileTests(unittest.TestCase):
    def test_valid_profile_canonicalizes_binding_order(self):
        a = _body_profile(order="bold-font")
        b = _body_profile(order="font-bold")
        self.assertEqual(a.canonical_bindings, b.canonical_bindings)

    def test_duplicate_binding_rejected(self):
        b1 = RuleBinding("body", "run", _bold_rule(False, "one"))
        b2 = RuleBinding("body", "run", _bold_rule(True, "two"))
        with self.assertRaises(ProcessingSessionContractError):
            _profile(b1, b2)

    def test_unsupported_p3_binding_rejected(self):
        rule = FormattingRule(
            "line", "P3", "spacing.line", RuleMode.EXACT,
            expected=LineSpacingValue("auto", Decimal("1.5"), "multiple"),
        )
        with self.assertRaises(ProcessingSessionContractError):
            RuleBinding("body", "run", rule)

    def test_unsupported_class_rejected(self):
        with self.assertRaises(ProcessingSessionContractError):
            RuleBinding("reference", "run", _bold_rule())

    def test_non_run_target_rejected(self):
        with self.assertRaises(ProcessingSessionContractError):
            RuleBinding("body", "paragraph", _bold_rule())

    def test_invalid_bold_rule_type_rejected_even_without_document_target(self):
        rule = FormattingRule("bad", "P1", "bold", RuleMode.EXACT, expected=1)
        with self.assertRaises(ProcessingSessionContractError):
            RuleBinding("body", "run", rule)

    def test_invalid_font_rule_type_rejected(self):
        rule = FormattingRule("bad", "P2", "font_size", RuleMode.EXACT, expected=12)
        with self.assertRaises(ProcessingSessionContractError):
            RuleBinding("body", "run", rule)

    def test_empty_profile_rejected(self):
        with self.assertRaises(ProcessingSessionContractError):
            ProcessingProfile(PROFILE_REF, ())


class ProcessingSessionRealFlowTests(unittest.TestCase):
    def test_no_change_is_quiescent_and_byte_identical(self):
        pkg = _pkg(_paragraph(_run("ok", bold=False, half_points=24)))
        result = process_document(pkg, _body_profile())
        self.assertEqual(result.processing_session_version, PROCESSING_SESSION_VERSION)
        self.assertEqual(result.status, ProcessingSessionStatus.QUIESCENT)
        self.assertEqual(result.output_package_bytes, pkg)
        self.assertEqual(result.input_package_sha256, result.output_package_sha256)
        self.assertEqual(result.transforms, ())
        self.assertEqual(result.findings, ())
        self.assertTrue(result.final_decisions)
        self.assertTrue(all(d.actionability is Actionability.NO_ACTION for d in result.final_decisions))

    def test_one_bold_change(self):
        pkg = _pkg(_paragraph(_run("bold", bold=True, half_points=24)))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        result = process_document(pkg, profile)
        self.assertEqual(result.status, ProcessingSessionStatus.QUIESCENT)
        self.assertEqual(len(result.transforms), 1)
        self.assertEqual(result.transforms[0].target.property_slot, "bold")
        state = _body_run_states(result.output_package_bytes)[0]
        self.assertIs(state[1].value, False)

    def test_one_paragraph_alignment_change(self):
        pkg = _pkg(
            '<w:p><w:pPr><w:jc w:val="left"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>align</w:t></w:r></w:p>'
        )
        profile = _profile(
            RuleBinding(
                "body",
                "paragraph",
                FormattingRule(
                    "body-alignment", "P4", "alignment", RuleMode.EXACT, expected="both"
                ),
            )
        )
        result = process_document(pkg, profile)
        self.assertEqual(result.status, ProcessingSessionStatus.QUIESCENT)
        self.assertEqual(len(result.transforms), 1)
        self.assertEqual(result.transforms[0].target.target_type, "paragraph")
        self.assertEqual(result.transforms[0].target.property_slot, "alignment")
        ir = DocxParser().parse_bytes(result.output_package_bytes)
        catalog = build_style_catalog(result.output_package_bytes, ir)
        resolved = resolve_paragraph_formatting(
            ir["stories"][0]["blocks"][0], catalog, "word/document.xml"
        )
        self.assertEqual(resolved.alignment.value, "both")

    def test_one_font_change(self):
        pkg = _pkg(_paragraph(_run("font", bold=False, half_points=22)))
        profile = _profile(RuleBinding("body", "run", _font_rule(Decimal("12"))))
        result = process_document(pkg, profile)
        self.assertEqual(result.status, ProcessingSessionStatus.QUIESCENT)
        self.assertEqual(len(result.transforms), 1)
        self.assertEqual(result.transforms[0].target.property_slot, "font_size")
        state = _body_run_states(result.output_package_bytes)[0]
        self.assertEqual(state[2].value.value, Decimal("12"))

    def test_bold_and_font_same_run_require_two_fresh_iterations(self):
        pkg = _two_change_pkg()
        calls = []

        def checked_apply(snapshot, token):
            self.assertEqual(
                hashlib.sha256(snapshot).hexdigest(), token.current_package_sha256
            )
            calls.append(token.current_package_sha256)
            return real_apply_cleared_operation(snapshot, token)

        with mock_patch(
            "formatador_academico.processing_session.engine.apply_cleared_operation",
            side_effect=checked_apply,
        ):
            result = process_document(pkg, _body_profile())

        self.assertEqual(result.status, ProcessingSessionStatus.QUIESCENT)
        self.assertEqual(len(result.transforms), 2)
        self.assertEqual(
            [t.target.property_slot for t in result.transforms], ["bold", "font_size"]
        )
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0], calls[1])
        self.assertEqual(result.transforms[0].output_package_sha256, calls[1])
        state = _body_run_states(result.output_package_bytes)[0]
        self.assertIs(state[1].value, False)
        self.assertEqual(state[2].value.value, Decimal("12"))

    def test_transform_chain_exactly_links_input_to_output(self):
        result = process_document(_two_change_pkg(), _body_profile())
        self.assertEqual(
            result.transforms[0].input_package_sha256, result.input_package_sha256
        )
        self.assertEqual(
            result.transforms[0].output_package_sha256,
            result.transforms[1].input_package_sha256,
        )
        self.assertEqual(
            result.transforms[-1].output_package_sha256, result.output_package_sha256
        )
        self.assertEqual(
            result.output_package_sha256,
            hashlib.sha256(result.output_package_bytes).hexdigest(),
        )

    def test_multiple_runs_apply_in_physical_order(self):
        pkg = _pkg(
            _paragraph(
                _run("first", bold=True, half_points=24),
                _run("second", bold=True, half_points=24),
            )
        )
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        result = process_document(pkg, profile)
        self.assertEqual(len(result.transforms), 2)
        paths = [t.target.structural_path for t in result.transforms]
        self.assertTrue(paths[0].endswith("/w:r[1]"), paths)
        self.assertTrue(paths[1].endswith("/w:r[2]"), paths)

    def test_multiple_paragraphs_apply_in_document_order(self):
        pkg = _pkg(
            _paragraph(_run("p1", bold=True, half_points=24))
            + _paragraph(_run("p2", bold=True, half_points=24))
        )
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        result = process_document(pkg, profile)
        self.assertEqual(len(result.transforms), 2)
        paths = [t.target.structural_path for t in result.transforms]
        self.assertIn("/w:p[1]/", paths[0])
        self.assertIn("/w:p[2]/", paths[1])

    def test_binding_caller_order_does_not_change_output_or_transform_order(self):
        pkg = _two_change_pkg()
        a = process_document(pkg, _body_profile(order="bold-font"))
        b = process_document(pkg, _body_profile(order="font-bold"))
        self.assertEqual(a.output_package_bytes, b.output_package_bytes)
        self.assertEqual(a.output_package_sha256, b.output_package_sha256)
        self.assertEqual(
            [transform_ref(x) for x in a.transforms],
            [transform_ref(x) for x in b.transforms],
        )

    def test_heading_binding_applies_only_to_heading(self):
        body = (
            _paragraph(_run("body", bold=True, half_points=24))
            + _paragraph(_run("head", bold=True, half_points=24), style="Heading1")
        )
        pkg = _pkg(body, styles=NORMAL + HEADING1)
        profile = _profile(RuleBinding("heading", "run", _bold_rule(False, "heading-bold")))
        result = process_document(pkg, profile)
        self.assertEqual(len(result.transforms), 1)
        self.assertEqual(result.transforms[0].target.target_class, "heading")
        states = _body_run_states(result.output_package_bytes)
        self.assertIs(states[0][1].value, True)
        self.assertIs(states[1][1].value, False)

    def test_run_inside_hyperlink_is_enumerated(self):
        body = (
            '<w:p><w:hyperlink w:anchor="x">'
            + _run("link", bold=True, half_points=24)
            + "</w:hyperlink></w:p>"
        )
        pkg = _pkg(body)
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        result = process_document(pkg, profile)
        self.assertEqual(len(result.transforms), 1)
        self.assertIn("w:hyperlink", result.transforms[0].target.structural_path)

    def test_final_classifications_are_from_final_snapshot(self):
        pkg = _two_change_pkg()
        result = process_document(pkg, _body_profile())
        ir = DocxParser().parse_bytes(result.output_package_bytes)
        catalog = build_style_catalog(result.output_package_bytes, ir)
        fresh = classify_document(ir, catalog)
        self.assertEqual(result.final_classifications, fresh)

    def test_classification_abstention_is_retained(self):
        table = (
            "<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w=\"1000\"/></w:tblGrid>"
            "<w:tr><w:tc><w:tcPr/>"
            + _paragraph(_run("cell", bold=True, half_points=24))
            + "</w:tc></w:tr></w:tbl>"
        )
        result = process_document(
            _pkg(table), _profile(RuleBinding("body", "run", _bold_rule(False)))
        )
        self.assertEqual(result.status, ProcessingSessionStatus.QUIESCENT)
        self.assertEqual(result.transforms, ())
        self.assertTrue(
            any(c.status is ClassificationStatus.ABSTAINED for c in result.final_classifications)
        )
        self.assertEqual(result.final_decisions, ())

    def test_input_bytes_are_not_modified(self):
        pkg = _two_change_pkg()
        before = bytes(pkg)
        process_document(pkg, _body_profile())
        self.assertEqual(pkg, before)


class ProcessingSessionFindingTests(unittest.TestCase):
    def test_global_gate_block_becomes_final_finding_and_never_calls_patcher(self):
        pkg = _pkg(_paragraph(_run("blocked", bold=True, half_points=24)))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))

        def block_gate(plan, decisions, ir, catalog, profile_ref):
            real = real_evaluate_operation_plan(plan, decisions, ir, catalog, profile_ref)
            reason = GateReason.PROFILE_CONTEXT_CHANGED
            blocked = tuple(
                GateResult(r.operation_ref, GateStatus.BLOCKED, (reason,), None)
                for r in real.results
            )
            return SafetyGateReport(
                real.safety_gate_version,
                real.operation_plan_ref,
                real.current_package_sha256,
                ContextStatus.BLOCKED,
                (reason,),
                blocked,
                (),
            )

        with mock_patch(
            "formatador_academico.processing_session.engine.evaluate_operation_plan",
            side_effect=block_gate,
        ), mock_patch(
            "formatador_academico.processing_session.engine.apply_cleared_operation"
        ) as patcher:
            result = process_document(pkg, profile)

        patcher.assert_not_called()
        self.assertEqual(result.status, ProcessingSessionStatus.QUIESCENT_WITH_UNAPPLIED)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].kind, SessionFindingKind.GATE_BLOCKED)
        self.assertEqual(result.findings[0].reason, GateReason.PROFILE_CONTEXT_CHANGED.value)

    def test_patch_rejection_does_not_stop_independent_later_operation(self):
        pkg = _pkg(
            _paragraph(
                _run("first", bold=True, half_points=24),
                _run("second", bold=True, half_points=24),
            )
        )
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))
        rejected_calls = []
        applied_calls = []

        def selective(snapshot, token):
            if token.operation.target.structural_path.endswith("/w:r[1]"):
                rejected_calls.append(token.current_package_sha256)
                return PatchResult(
                    PATCHER_VERSION,
                    PatchStatus.REJECTED,
                    token.operation_ref,
                    token.operation_plan_ref,
                    token.current_package_sha256,
                    None,
                    None,
                    PatchReason.NONCANONICAL_RUN_PROPERTIES,
                    None,
                )
            applied_calls.append(token.current_package_sha256)
            return real_apply_cleared_operation(snapshot, token)

        with mock_patch(
            "formatador_academico.processing_session.engine.apply_cleared_operation",
            side_effect=selective,
        ):
            result = process_document(pkg, profile)

        self.assertEqual(result.status, ProcessingSessionStatus.QUIESCENT_WITH_UNAPPLIED)
        self.assertEqual(len(result.transforms), 1)
        self.assertEqual(len(applied_calls), 1)
        # rejection is attempted once on input snapshot and again after the
        # independent applied patch creates a fresh snapshot.
        self.assertEqual(len(rejected_calls), 2)
        self.assertNotEqual(rejected_calls[0], rejected_calls[1])
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].kind, SessionFindingKind.PATCH_REJECTED)
        self.assertEqual(
            result.findings[0].reason, PatchReason.NONCANONICAL_RUN_PROPERTIES.value
        )
        states = _body_run_states(result.output_package_bytes)
        self.assertIs(states[0][1].value, True)
        self.assertIs(states[1][1].value, False)

    def test_impossible_snapshot_rejection_is_integrity_error(self):
        pkg = _pkg(_paragraph(_run("x", bold=True, half_points=24)))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))

        def impossible(snapshot, token):
            return PatchResult(
                PATCHER_VERSION,
                PatchStatus.REJECTED,
                token.operation_ref,
                token.operation_plan_ref,
                token.current_package_sha256,
                None,
                None,
                PatchReason.SNAPSHOT_HASH_MISMATCH,
                None,
            )

        with mock_patch(
            "formatador_academico.processing_session.engine.apply_cleared_operation",
            side_effect=impossible,
        ):
            with self.assertRaises(ProcessingSessionIntegrityError):
                process_document(pkg, profile)

    def test_operation_limit_stops_before_next_patch(self):
        result = process_document(
            _two_change_pkg(), _body_profile(), max_applied_operations=1
        )
        self.assertEqual(result.status, ProcessingSessionStatus.OPERATION_LIMIT_REACHED)
        self.assertEqual(len(result.transforms), 1)
        self.assertEqual(result.transforms[0].target.property_slot, "bold")
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].kind, SessionFindingKind.OPERATION_LIMIT)
        self.assertEqual(result.findings[0].target.property_slot, "font_size")

    def test_cycle_detection_is_fail_fast(self):
        pkg = _pkg(_paragraph(_run("cycle", bold=True, half_points=24)))
        profile = _profile(RuleBinding("body", "run", _bold_rule(False)))

        def same_bytes(snapshot, token):
            return PatchResult(
                PATCHER_VERSION,
                PatchStatus.APPLIED,
                token.operation_ref,
                token.operation_plan_ref,
                token.current_package_sha256,
                hashlib.sha256(snapshot).hexdigest(),
                snapshot,
                None,
                "word/document.xml",
            )

        with mock_patch(
            "formatador_academico.processing_session.engine.apply_cleared_operation",
            side_effect=same_bytes,
        ):
            with self.assertRaises(ProcessingSessionIntegrityError):
                process_document(pkg, profile)


class ProcessingSessionInputAndDeterminismTests(unittest.TestCase):
    def test_bad_max_operations_rejected(self):
        pkg = _two_change_pkg()
        profile = _body_profile()
        for bad in (True, False, 0, -1, Decimal("1")):
            with self.subTest(bad=bad):
                with self.assertRaises(ProcessingSessionContractError):
                    process_document(pkg, profile, max_applied_operations=bad)

    def test_non_bytes_input_rejected(self):
        with self.assertRaises(ProcessingSessionContractError):
            process_document(bytearray(b"x"), _body_profile())

    def test_invalid_docx_rejected(self):
        with self.assertRaises(ProcessingSessionContractError):
            process_document(b"not a docx", _body_profile())

    def test_repeated_runs_are_deterministic(self):
        pkg = _two_change_pkg()
        profile = _body_profile()
        a = process_document(pkg, profile)
        b = process_document(pkg, profile)
        self.assertEqual(a, b)
        self.assertEqual(a.output_package_bytes, b.output_package_bytes)

    def test_hashseed_determinism_subprocess(self):
        code = r'''
import json
from decimal import Decimal
from formatador_academico.decision import FormattingRule, ProfileRef, RuleMode
from formatador_academico.processing_session import ProcessingProfile, RuleBinding, process_document
from formatador_academico.transform_log import transform_ref
from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL
run = '<w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr><w:t>x</w:t></w:r>'
pkg = build_docx(document('<w:p>'+run+'</w:p>'), styles_part(NORMAL))
profile = ProcessingProfile(ProfileRef('session-profile','1'), (
    RuleBinding('body','run',FormattingRule('b','P1','bold',RuleMode.EXACT,expected=False)),
    RuleBinding('body','run',FormattingRule('f','P2','font_size',RuleMode.EXACT,expected=Decimal('12'))),
))
r = process_document(pkg, profile)
print(json.dumps({'sha':r.output_package_sha256,'refs':[transform_ref(t) for t in r.transforms]}, sort_keys=True))
'''
        outputs = []
        root = os.path.dirname(os.path.dirname(__file__))
        for seed in ("1", "2", "17", "99"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = os.pathsep.join(
                [os.path.join(root, "src"), os.path.join(root, "tests")]
            )
            out = subprocess.check_output(
                [sys.executable, "-c", code], cwd=root, env=env, text=True
            ).strip()
            outputs.append(json.loads(out))
        self.assertTrue(all(item == outputs[0] for item in outputs[1:]), outputs)

    def test_runtime_has_no_forbidden_io_clock_random_network_imports(self):
        from pathlib import Path
        import formatador_academico.processing_session.engine as engine

        source = Path(engine.__file__).read_text(encoding="utf-8")
        forbidden = (
            "import time",
            "from time",
            "import random",
            "from random",
            "import requests",
            "import socket",
            "urllib",
            "open(",
            "datetime.now",
            "uuid",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
