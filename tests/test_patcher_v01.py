"""Patcher v0.1 — unit/integration tests (decision 0028 §26).

Covers the mandatory scenario list of decision 0028: snapshot/TOCTOU
precondition, token-forgery rechecks, integrity fail-fast paths, rPr shape
rejections, canonical schema-order insertion, bold/font-size semantics,
w:szCs blind spot, direct-children-only enforcement, rPrChange protection,
XML prolog/docinfo preservation, ZIP metadata preservation, content
conservation, allowed-delta validator, determinism and stale second-token
behavior. E2E pipeline tests live in test_patcher_v01_e2e.py.
"""

from __future__ import annotations

import hashlib
import io
import unittest
import zipfile
from dataclasses import replace
from decimal import Decimal

from lxml import etree

from formatador_academico import parser_api
from formatador_academico.decision.model import DecisionKey
from formatador_academico.docx_parser import DocxParser, W_NS
from formatador_academico.operation_plan.model import (
    LengthValue,
    OperationKind,
    OperationTarget,
    PlannedOperation,
)
from formatador_academico.operation_plan.serialization import operation_ref
from formatador_academico.patcher import (
    PATCHER_VERSION,
    PatchReason,
    PatchResult,
    PatchStatus,
    PatcherContractError,
    PatcherIntegrityError,
    apply_cleared_operation,
)
from formatador_academico.patcher.validation import validate_allowed_delta
from formatador_academico.patcher.package import repackage
from formatador_academico.patcher.xml_patch import RPR_CANONICAL_ORDER
from formatador_academico.safety_gate.model import _EMISSION_PROOF, GateClearedOperation
from formatador_academico.safety_gate.targets import walk_records

from test_analysis_formatting_v01b_m1 import (
    FIXED_ZIP_DATE_TIME,
    build_docx,
    document,
    styles_part,
)

MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _first_run(pkg: bytes):
    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    for record, _ in walk_records(ir["stories"][0]["blocks"]):
        if record["source_type"] == "run_raw":
            return record
    raise AssertionError("no run found")


def _token(pkg, record, slot, precondition, desired, *, path=None, phash=None):
    aspect = {"bold": "P1", "font_size": "P2"}[slot]
    key = DecisionKey("run", aspect, slot)
    target = OperationTarget(
        target_type="run",
        structural_path=path or record["structural_path"],
        physical_hash=phash or record["physical_hash"],
        target_class="body",
        aspect_id=aspect,
        property_slot=slot,
    )
    operation = PlannedOperation(
        kind=OperationKind.SET_PROPERTY,
        key=key,
        target=target,
        precondition_observed=precondition,
        desired_value=desired,
        decision_ref="0" * 64,
    )
    return GateClearedOperation(
        operation=operation,
        operation_ref=operation_ref(operation),
        operation_plan_ref="1" * 64,
        current_package_sha256=_sha(pkg),
        _proof=_EMISSION_PROOF,
    )


def _bold_token(pkg, body=None, desired=False, **kw):
    record = _first_run(pkg)
    return _token(pkg, record, "bold", not desired, desired, **kw)


def _font_token(pkg, desired=Decimal("12"), precondition=Decimal("11"), **kw):
    record = _first_run(pkg)
    return _token(
        pkg, record, "font_size",
        LengthValue(precondition, "pt"), LengthValue(desired, "pt"), **kw,
    )


def _pkg(body, styles=None, **kw):
    return build_docx(document(body), styles, **kw)


def _out_doc(result) -> str:
    return zipfile.ZipFile(io.BytesIO(result.output_package_bytes)).read(
        "word/document.xml"
    ).decode("utf-8")


BOLD_RUN = '<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>a</w:t></w:r></w:p>'


class TestModelInvariants(unittest.TestCase):
    def test_version(self):
        self.assertEqual(PATCHER_VERSION, "0.1")

    def test_applied_invariants(self):
        with self.assertRaises(ValueError):
            PatchResult(PATCHER_VERSION, PatchStatus.APPLIED, "0" * 64, "1" * 64,
                        "2" * 64, "3" * 64, None, None, "word/document.xml")
        with self.assertRaises(ValueError):
            PatchResult(PATCHER_VERSION, PatchStatus.APPLIED, "0" * 64, "1" * 64,
                        "2" * 64, "3" * 64, b"x", PatchReason.UNSUPPORTED_OPERATION,
                        "word/document.xml")

    def test_rejected_invariants(self):
        with self.assertRaises(ValueError):
            PatchResult(PATCHER_VERSION, PatchStatus.REJECTED, "0" * 64, "1" * 64,
                        "2" * 64, None, None, None, None)
        with self.assertRaises(ValueError):
            PatchResult(PATCHER_VERSION, PatchStatus.REJECTED, "0" * 64, "1" * 64,
                        "2" * 64, None, b"x", PatchReason.UNSUPPORTED_OPERATION, None)
        ok = PatchResult(PATCHER_VERSION, PatchStatus.REJECTED, "0" * 64, "1" * 64,
                         "2" * 64, None, None, PatchReason.SNAPSHOT_HASH_MISMATCH, None)
        self.assertEqual(ok.status, PatchStatus.REJECTED)


class TestSnapshotAndContract(unittest.TestCase):
    # scenario 1
    def test_snapshot_hash_mismatch_rejects_without_output(self):
        pkg = _pkg(BOLD_RUN)
        token = _bold_token(pkg)
        other = _pkg('<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>b</w:t></w:r></w:p>')
        result = apply_cleared_operation(other, token)
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.SNAPSHOT_HASH_MISMATCH)
        self.assertIsNone(result.output_package_bytes)
        self.assertIsNone(result.output_package_sha256)
        self.assertEqual(result.input_package_sha256, _sha(other))

    # scenario 2
    def test_raw_planned_operation_is_contract_error(self):
        pkg = _pkg(BOLD_RUN)
        token = _bold_token(pkg)
        with self.assertRaises(PatcherContractError):
            apply_cleared_operation(pkg, token.operation)
        with self.assertRaises(PatcherContractError):
            apply_cleared_operation(pkg, "not-a-token")
        with self.assertRaises(PatcherContractError):
            apply_cleared_operation("not-bytes", token)

    def test_unsupported_operation_rejected(self):
        pkg = _pkg(BOLD_RUN)
        record = _first_run(pkg)
        key = DecisionKey("run", "P1", "italic")  # known slot, outside v0.1 slice
        target = OperationTarget("run", record["structural_path"],
                                 record["physical_hash"], "body", "P1", "italic")
        operation = PlannedOperation(OperationKind.SET_PROPERTY, key, target,
                                     True, False, "0" * 64)
        token = GateClearedOperation(
            operation=operation, operation_ref=operation_ref(operation),
            operation_plan_ref="1" * 64, current_package_sha256=_sha(pkg),
            _proof=_EMISSION_PROOF)
        result = apply_cleared_operation(pkg, token)
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.UNSUPPORTED_OPERATION)


class TestTokenForgeryRechecks(unittest.TestCase):
    # scenario 3/5: fabricated token (consistent refs, wrong physical hash)
    def test_fabricated_token_wrong_physical_hash_is_integrity_error(self):
        pkg = _pkg(BOLD_RUN)
        record = _first_run(pkg)
        bogus = "f" * 64
        assert bogus != record["physical_hash"]
        token = _token(pkg, record, "bold", True, False, phash=bogus)
        with self.assertRaises(PatcherIntegrityError):
            apply_cleared_operation(pkg, token)

    # scenario 4: path drift after a matching snapshot
    def test_unresolvable_path_is_integrity_error(self):
        pkg = _pkg(BOLD_RUN)
        record = _first_run(pkg)
        token = _token(pkg, record, "bold", True, False,
                       path="/w:document/w:body[1]/w:p[1]/w:r[9]")
        with self.assertRaises(PatcherIntegrityError):
            apply_cleared_operation(pkg, token)

    def test_path_resolving_to_non_run_is_integrity_error(self):
        pkg = _pkg(BOLD_RUN)
        record = _first_run(pkg)
        token = _token(pkg, record, "bold", True, False,
                       path="/w:document/w:body[1]/w:p[1]",
                       phash=record["physical_hash"])
        with self.assertRaises(PatcherIntegrityError):
            apply_cleared_operation(pkg, token)

    # scenario 3b: dataclasses.replace cannot desynchronize the embedded op
    def test_replace_cannot_desync_operation_ref(self):
        pkg = _pkg(BOLD_RUN)
        token = _bold_token(pkg)
        other = _token(pkg, _first_run(pkg), "font_size",
                       LengthValue(Decimal("11"), "pt"), LengthValue(Decimal("12"), "pt"))
        with self.assertRaises(Exception):
            replace(token, operation=other.operation)


class TestRPrShape(unittest.TestCase):
    # scenario 6
    def test_duplicate_rpr_rejected(self):
        pkg = _pkg('<w:p><w:r><w:rPr><w:b/></w:rPr><w:rPr><w:i/></w:rPr>'
                   '<w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.NONCANONICAL_RUN_PROPERTIES)

    # scenario 7
    def test_misplaced_rpr_rejected(self):
        pkg = _pkg('<w:p><w:r><w:t>a</w:t><w:rPr><w:b/></w:rPr></w:r></w:p>')
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.NONCANONICAL_RUN_PROPERTIES)

    # scenario 8
    def test_empty_rpr_reused(self):
        pkg = _pkg('<w:p><w:r><w:rPr/><w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _bold_token(pkg, desired=True,
                                                         ))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        doc = _out_doc(result)
        self.assertEqual(doc.count("<w:rPr>"), 1)
        self.assertIn("<w:b/>", doc)

    # scenario 12
    def test_alternate_content_in_rpr_rejected(self):
        body = (f'<w:p><w:r><w:rPr><mc:AlternateContent xmlns:mc="{MC}">'
                f'<mc:Fallback/></mc:AlternateContent></w:rPr><w:t>a</w:t></w:r></w:p>')
        pkg = _pkg(body)
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.NONCANONICAL_RUN_PROPERTIES)

    # scenario 13
    def test_out_of_order_rpr_children_rejected(self):
        pkg = _pkg('<w:p><w:r><w:rPr><w:i/><w:b/></w:rPr><w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _font_token(pkg, precondition=Decimal("11")))
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.NONCANONICAL_RUN_PROPERTIES)

    # scenario 9
    def test_duplicate_bold_rejected(self):
        pkg = _pkg('<w:p><w:r><w:rPr><w:b/><w:b w:val="0"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.DUPLICATE_TARGET_PROPERTY)

    # scenario 10
    def test_duplicate_sz_rejected(self):
        pkg = _pkg('<w:p><w:r><w:rPr><w:sz w:val="22"/><w:sz w:val="22"/></w:rPr>'
                   '<w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _font_token(pkg))
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.DUPLICATE_TARGET_PROPERTY)

    # scenarios 11 + 36: rPrChange content does not count and stays intact
    def test_rprchange_nested_properties_protected(self):
        body = ('<w:p><w:r><w:rPr><w:b/><w:rPrChange w:id="7" w:author="x" '
                'w:date="2020-01-01T00:00:00Z"><w:rPr><w:b/><w:sz w:val="20"/>'
                '</w:rPr></w:rPrChange></w:rPr><w:t>a</w:t></w:r></w:p>')
        pkg = _pkg(body)
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        doc = _out_doc(result)
        self.assertIn('<w:rPrChange w:id="7" w:author="x" '
                      'w:date="2020-01-01T00:00:00Z"><w:rPr><w:b/><w:sz w:val="20"/>'
                      '</w:rPr></w:rPrChange>', doc)
        self.assertIn('<w:rPr><w:b w:val="0"/><w:rPrChange', doc)


class TestCanonicalOrder(unittest.TestCase):
    def test_rank_table_matches_contract_reference(self):
        self.assertEqual(RPR_CANONICAL_ORDER, (
            "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps",
            "strike", "dstrike", "outline", "shadow", "emboss", "imprint",
            "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
            "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
            "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
            "eastAsianLayout", "specVanish", "oMath", "rPrChange",
        ))

    # scenario 14
    def test_dense_rpr_bold_insertion_position(self):
        body = ('<w:p><w:r><w:rPr><w:rFonts w:ascii="Arial"/><w:i/>'
                '<w:color w:val="FF0000"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        pkg = _pkg(body)
        result = apply_cleared_operation(pkg, _bold_token(pkg, desired=True))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        doc = _out_doc(result)
        self.assertIn('<w:rPr><w:rFonts w:ascii="Arial"/><w:b/><w:i/>'
                      '<w:color w:val="FF0000"/></w:rPr>', doc)

    # scenario 15
    def test_dense_rpr_sz_insertion_position(self):
        body = ('<w:p><w:r><w:rPr><w:color w:val="FF0000"/><w:szCs w:val="24"/>'
                '<w:highlight w:val="yellow"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        pkg = _pkg(body)
        result = apply_cleared_operation(pkg, _font_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        doc = _out_doc(result)
        self.assertIn('<w:rPr><w:color w:val="FF0000"/><w:sz w:val="24"/>'
                      '<w:szCs w:val="24"/><w:highlight w:val="yellow"/></w:rPr>', doc)

    # scenario 27: w:szCs is never touched, even when divergent
    def test_szcs_untouched(self):
        body = ('<w:p><w:r><w:rPr><w:sz w:val="22"/><w:szCs w:val="30"/></w:rPr>'
                '<w:t>a</w:t></w:r></w:p>')
        pkg = _pkg(body)
        result = apply_cleared_operation(pkg, _font_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        doc = _out_doc(result)
        self.assertIn('<w:sz w:val="24"/><w:szCs w:val="30"/>', doc)


class TestBoldSemantics(unittest.TestCase):
    # scenario 16
    def test_bold_true_normalizes_to_bare_element(self):
        pkg = _pkg('<w:p><w:r><w:rPr><w:b w:val="true"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _bold_token(pkg, desired=True))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn("<w:b/>", _out_doc(result))
        self.assertNotIn('w:val="true"', _out_doc(result))

    # scenario 18
    def test_bold_false_from_direct_true(self):
        pkg = _pkg(BOLD_RUN)
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:b w:val="0"/>', _out_doc(result))

    # scenario 19
    def test_bold_true_from_direct_false(self):
        pkg = _pkg('<w:p><w:r><w:rPr><w:b w:val="0"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _bold_token(pkg, desired=True))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn("<w:b/>", _out_doc(result))

    # scenario 17: inherited bold (paragraph style) defeated by w:val="0"
    def test_bold_false_defeats_inherited_true(self):
        styles = styles_part(
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/><w:rPr><w:b/></w:rPr></w:style>')
        pkg = _pkg('<w:p><w:r><w:t>a</w:t></w:r></w:p>', styles)
        result = apply_cleared_operation(pkg, _bold_token(pkg, desired=False))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:b w:val="0"/>', _out_doc(result))
        ir = DocxParser().parse_bytes(result.output_package_bytes)
        from formatador_academico.analysis.formatting import resolve_run_formatting
        from formatador_academico.analysis.style_catalog import build_style_catalog
        catalog = build_style_catalog(result.output_package_bytes, ir)
        run = _first_run(result.output_package_bytes)
        paragraph = ir["stories"][0]["blocks"][0]
        analysis = resolve_run_formatting(run, paragraph, catalog, "word/document.xml")
        self.assertIs(analysis.bold.value, False)

    # scenario 20
    def test_create_rpr_for_bold(self):
        pkg = _pkg('<w:p><w:r><w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _bold_token(pkg, desired=True))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:r><w:rPr><w:b/></w:rPr><w:t>a</w:t></w:r>', _out_doc(result))


class TestFontSizeSemantics(unittest.TestCase):
    # scenario 21
    def test_font_11_to_12(self):
        pkg = _pkg('<w:p><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _font_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:sz w:val="24"/>', _out_doc(result))

    # scenario 22 + 23: inherited/absent font size creates direct w:sz (and rPr)
    def test_create_rpr_for_font(self):
        pkg = _pkg('<w:p><w:r><w:t>a</w:t></w:r></w:p>')
        result = apply_cleared_operation(pkg, _font_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>a</w:t></w:r>',
                      _out_doc(result))

    # scenario 24
    def test_half_point_value(self):
        pkg = _pkg(BOLD_RUN)
        result = apply_cleared_operation(
            pkg, _font_token(pkg, desired=Decimal("11.5"), precondition=Decimal("11")))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:sz w:val="23"/>', _out_doc(result))

    # scenario 25: no rounding
    def test_non_half_point_rejected(self):
        pkg = _pkg(BOLD_RUN)
        result = apply_cleared_operation(
            pkg, _font_token(pkg, desired=Decimal("11.25"), precondition=Decimal("11")))
        self.assertEqual(result.status, PatchStatus.REJECTED)
        self.assertEqual(result.reason, PatchReason.UNREPRESENTABLE_VALUE)
        self.assertIsNone(result.output_package_bytes)

    # scenario 26
    def test_zero_negative_out_of_range_rejected(self):
        pkg = _pkg(BOLD_RUN)
        for bad in ("0", "-1", "1638.5", "2000"):
            result = apply_cleared_operation(
                pkg, _font_token(pkg, desired=Decimal(bad), precondition=Decimal("11")))
            self.assertEqual(result.status, PatchStatus.REJECTED, bad)
            self.assertEqual(result.reason, PatchReason.UNREPRESENTABLE_VALUE, bad)

    def test_boundary_1638pt_accepted(self):
        pkg = _pkg(BOLD_RUN)
        result = apply_cleared_operation(
            pkg, _font_token(pkg, desired=Decimal("1638"), precondition=Decimal("11")))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:sz w:val="3276"/>', _out_doc(result))


class TestStructuralPathResolution(unittest.TestCase):
    # scenario 28: non-w namespace segment; the resolver is NOT XPath
    def test_non_w_namespace_roundtrip_without_xpath(self):
        xml = (f'<w:document xmlns:w="{W_NS}" xmlns:x="urn:x">'
               f'<w:body><x:blk/><x:blk/><w:p><w:r><w:t>a</w:t></w:r></w:p>'
               f'</w:body></w:document>')
        root = etree.fromstring(xml.encode())
        body = root[0]
        foreign = body[1]
        path = parser_api.structural_path(foreign, root)
        self.assertEqual(path, "/w:document/w:body[1]/{urn:x}blk[2]")
        resolved = parser_api.resolve_structural_path(root, path)
        self.assertIs(resolved, foreign)
        # proof the string is not fed to an XPath engine: it is invalid XPath
        with self.assertRaises(Exception):
            root.xpath(path)

    def test_comment_and_pi_segments(self):
        xml = (f'<w:document xmlns:w="{W_NS}"><w:body><!--c--><?p i?>'
               f'<w:p><w:r><w:t>a</w:t></w:r></w:p></w:body></w:document>')
        root = etree.fromstring(xml.encode())
        body = root[0]
        comment = body[0]
        pi = body[1]
        for node in (comment, pi):
            path = parser_api.structural_path(node, root)
            self.assertIs(parser_api.resolve_structural_path(root, path), node)

    # scenario 29
    def test_run_inside_hyperlink_resolves(self):
        body = ('<w:p><w:hyperlink><w:r><w:rPr><w:b/></w:rPr>'
                '<w:t>a</w:t></w:r></w:hyperlink></w:p>')
        pkg = _pkg(body)
        record = _first_run(pkg)
        self.assertIn("w:hyperlink[1]", record["structural_path"])
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:b w:val="0"/>', _out_doc(result))

    # scenario 30
    def test_run_inside_table_cell_resolves(self):
        body = ('<w:tbl><w:tblGrid><w:gridCol w:w="100"/></w:tblGrid>'
                '<w:tr><w:tc><w:p><w:r><w:rPr><w:b/></w:rPr>'
                '<w:t>a</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
        pkg = _pkg(body)
        record = _first_run(pkg)
        self.assertIn("w:tbl[1]", record["structural_path"])
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        self.assertIn('<w:b w:val="0"/>', _out_doc(result))


class TestPrologPreservation(unittest.TestCase):
    # scenarios 31 + 32
    def test_prolog_comment_pi_and_standalone_preserved(self):
        doc_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   '<!--pre--><?pi data?>'
                   f'<w:document xmlns:w="{W_NS}"><w:body>'
                   '<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>a</w:t></w:r></w:p>'
                   '</w:body></w:document><!--post-->')
        pkg = build_docx(doc_xml)
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        raw = zipfile.ZipFile(io.BytesIO(result.output_package_bytes)).read(
            "word/document.xml")
        self.assertTrue(raw.startswith(
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'))
        self.assertIn(b"<!--pre-->", raw)
        self.assertIn(b"<?pi data?>", raw)
        self.assertIn(b"<!--post-->", raw)
        self.assertIn(b'<w:b w:val="0"/>', raw)


def _rich_package():
    """Package exercising ZIP metadata: STORED part, directory entry,
    per-entry comments, archive comment and untouched payload parts."""

    body = ('<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>a</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>keep</w:t><w:tab/><w:br/>'
            '<w:sym w:font="Symbol" w:char="F041"/></w:r></w:p>'
            '<w:p><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText>'
            '</w:r></w:p>')
    styles = styles_part('<w:style w:type="paragraph" w:default="1" '
                         'w:styleId="Normal"><w:name w:val="Normal"/></w:style>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.comment = b"archive-comment"
        ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
              '</Types>')
        info = zipfile.ZipInfo("[Content_Types].xml", FIXED_ZIP_DATE_TIME)
        info.comment = b"ct-comment"
        z.writestr(info, ct)
        z.writestr(zipfile.ZipInfo("_rels/.rels", FIXED_ZIP_DATE_TIME),
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                   'Target="word/document.xml"/></Relationships>')
        directory = zipfile.ZipInfo("customXml/", FIXED_ZIP_DATE_TIME)
        directory.external_attr = 0o40775 << 16 | 0x10
        z.writestr(directory, b"")
        stored = zipfile.ZipInfo("customXml/item1.xml", FIXED_ZIP_DATE_TIME,
                                 )
        stored.compress_type = zipfile.ZIP_STORED
        stored.comment = b"stored-comment"
        stored.external_attr = 0o100644 << 16
        z.writestr(stored, b"<stored/>")
        z.writestr(zipfile.ZipInfo("word/document.xml", FIXED_ZIP_DATE_TIME),
                   document(body).encode())
        z.writestr(zipfile.ZipInfo("word/styles.xml", FIXED_ZIP_DATE_TIME),
                   styles.encode())
    return buf.getvalue()


class TestPackagePreservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pkg = _rich_package()
        cls.result = apply_cleared_operation(cls.pkg, _bold_token(cls.pkg))
        assert cls.result.status is PatchStatus.APPLIED
        cls.zin = zipfile.ZipFile(io.BytesIO(cls.pkg))
        cls.zout = zipfile.ZipFile(io.BytesIO(cls.result.output_package_bytes))

    # scenario 38 + 39
    def test_entry_set_and_order_unchanged(self):
        self.assertEqual(self.zin.namelist(), self.zout.namelist())

    # scenario 37
    def test_untouched_parts_byte_identical(self):
        for name in self.zin.namelist():
            if name == "word/document.xml":
                continue
            self.assertEqual(self.zin.read(name), self.zout.read(name), name)

    # scenario 40
    def test_stored_entry_remains_stored(self):
        out = self.zout.getinfo("customXml/item1.xml")
        self.assertEqual(out.compress_type, zipfile.ZIP_STORED)

    # scenario 41
    def test_directory_entry_metadata_preserved(self):
        before = self.zin.getinfo("customXml/")
        after = self.zout.getinfo("customXml/")
        self.assertTrue(after.is_dir())
        self.assertEqual(before.external_attr, after.external_attr)
        self.assertEqual(before.date_time, after.date_time)
        self.assertEqual(before.create_system, after.create_system)

    # scenario 42
    def test_comments_preserved(self):
        self.assertEqual(self.zin.comment, self.zout.comment)
        for name in ("[Content_Types].xml", "customXml/item1.xml"):
            self.assertEqual(self.zin.getinfo(name).comment,
                             self.zout.getinfo(name).comment)

    def test_metadata_allowlist_preserved(self):
        for name in self.zin.namelist():
            before, after = self.zin.getinfo(name), self.zout.getinfo(name)
            for attr in ("filename", "date_time", "compress_type",
                         "external_attr", "internal_attr", "create_system"):
                self.assertEqual(getattr(before, attr), getattr(after, attr),
                                 f"{name}:{attr}")

    def test_no_current_timestamp_leaks(self):
        for name in self.zout.namelist():
            self.assertEqual(self.zout.getinfo(name).date_time,
                             FIXED_ZIP_DATE_TIME)


class TestZeroExternalAttrPreservation(unittest.TestCase):
    def test_zero_external_attr_survives_repackage(self):
        info = zipfile.ZipInfo("word/document.xml", FIXED_ZIP_DATE_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0
        output = repackage(
            [info], {"word/document.xml": b"<document/>"}, b"", b"<document/>"
        )
        with zipfile.ZipFile(io.BytesIO(output), "r") as zf:
            self.assertEqual(zf.getinfo("word/document.xml").external_attr, 0)


class TestContentConservation(unittest.TestCase):
    # scenarios 33/34/35 + 29 (container text) — directed conservation checks
    def test_text_fragments_and_containers_preserved(self):
        body = (
            '<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>a</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>keep</w:t><w:tab/><w:br/>'
            '<w:sym w:font="Symbol" w:char="F041"/></w:r></w:p>'
            '<w:p><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText>'
            '</w:r></w:p>'
            '<w:p><w:del><w:r><w:delText>old</w:delText></w:r></w:del></w:p>'
            '<w:p><w:hyperlink><w:r><w:t>link</w:t></w:r></w:hyperlink></w:p>'
        )
        pkg = _pkg(body)
        result = apply_cleared_operation(pkg, _bold_token(pkg))
        self.assertEqual(result.status, PatchStatus.APPLIED)
        doc = _out_doc(result)
        for fragment in (
            "<w:t>keep</w:t>", "<w:tab/>", "<w:br/>",
            '<w:sym w:font="Symbol" w:char="F041"/>',
            '<w:instrText xml:space="preserve"> PAGE </w:instrText>',
            "<w:delText>old</w:delText>",
            "<w:hyperlink><w:r><w:t>link</w:t></w:r></w:hyperlink>",
        ):
            self.assertIn(fragment, doc)


class TestAllowedDeltaValidator(unittest.TestCase):
    # scenario 43
    def test_validator_catches_unrelated_mutation(self):
        pkg = _pkg(BOLD_RUN)
        record = _first_run(pkg)
        original = zipfile.ZipFile(io.BytesIO(pkg)).read("word/document.xml")
        tampered = original.replace(b"<w:t>a</w:t>", b"<w:t>b</w:t>")
        with self.assertRaises(PatcherIntegrityError):
            validate_allowed_delta(original, tampered,
                                   record["structural_path"], "bold", False)

    def test_validator_catches_rprchange_neutralization(self):
        body = ('<w:p><w:r><w:rPr><w:b/><w:rPrChange w:id="7" w:author="x" '
                'w:date="2020-01-01T00:00:00Z"><w:rPr><w:b/></w:rPr>'
                '</w:rPrChange></w:rPr><w:t>a</w:t></w:r></w:p>')
        pkg = _pkg(body)
        record = _first_run(pkg)
        original = zipfile.ZipFile(io.BytesIO(pkg)).read("word/document.xml")
        # simulate a serializer that dropped the change-history container
        start = original.index(b"<w:rPrChange")
        end = original.index(b"</w:rPrChange>") + len(b"</w:rPrChange>")
        tampered = original[:start] + original[end:]
        with self.assertRaises(PatcherIntegrityError):
            validate_allowed_delta(original, tampered,
                                   record["structural_path"], "bold", False)


class TestDeterminismAndAtomicity(unittest.TestCase):
    # scenario 46 (plus the build_docx helper determinism, decision 0028 §33)
    def test_repeated_output_bytes_identical(self):
        pkg = _rich_package()
        token = _bold_token(pkg)
        first = apply_cleared_operation(pkg, token)
        second = apply_cleared_operation(pkg, token)
        self.assertEqual(first.status, PatchStatus.APPLIED)
        self.assertEqual(first.output_package_bytes, second.output_package_bytes)
        self.assertEqual(first.output_package_sha256, second.output_package_sha256)

    def test_build_docx_helper_deterministic(self):
        a = build_docx(document(BOLD_RUN), styles_part(""))
        b = build_docx(document(BOLD_RUN), styles_part(""))
        self.assertEqual(a, b)

    # scenario 47: the second same-report token goes stale after the first
    def test_second_token_stale_after_first_patch(self):
        pkg = _pkg('<w:p><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr>'
                   '<w:t>a</w:t></w:r></w:p>')
        record = _first_run(pkg)
        bold = _token(pkg, record, "bold", True, False)
        font = _token(pkg, record, "font_size",
                      LengthValue(Decimal("11"), "pt"),
                      LengthValue(Decimal("12"), "pt"))
        first = apply_cleared_operation(pkg, bold)
        self.assertEqual(first.status, PatchStatus.APPLIED)
        stale = apply_cleared_operation(first.output_package_bytes, font)
        self.assertEqual(stale.status, PatchStatus.REJECTED)
        self.assertEqual(stale.reason, PatchReason.SNAPSHOT_HASH_MISMATCH)


class TestPostconditionOnRelreadBytes(unittest.TestCase):
    # scenarios 44/45: the applied output re-parses and the public Analysis
    # observes exactly the desired semantic value (hash/text preserved).
    def test_postcondition_analysis_matches_desired(self):
        from formatador_academico.analysis.formatting import resolve_run_formatting
        from formatador_academico.analysis.style_catalog import build_style_catalog

        pkg = _pkg('<w:p><w:r><w:rPr><w:b/><w:sz w:val="22"/></w:rPr>'
                   '<w:t>a</w:t></w:r></w:p>')
        record = _first_run(pkg)
        token = _token(pkg, record, "font_size",
                       LengthValue(Decimal("11"), "pt"),
                       LengthValue(Decimal("12"), "pt"))
        result = apply_cleared_operation(pkg, token)
        self.assertEqual(result.status, PatchStatus.APPLIED)
        out = result.output_package_bytes
        ir = DocxParser().parse_bytes(out)
        self.assertEqual(ir["status"], "ok")
        new_record = _first_run(out)
        self.assertNotEqual(new_record["physical_hash"], record["physical_hash"])
        catalog = build_style_catalog(out, ir)
        paragraph = ir["stories"][0]["blocks"][0]
        analysis = resolve_run_formatting(new_record, paragraph, catalog,
                                          "word/document.xml")
        self.assertEqual(analysis.font_size.value.value, Decimal("12"))
        self.assertIs(analysis.bold.value, True)


if __name__ == "__main__":
    unittest.main()
