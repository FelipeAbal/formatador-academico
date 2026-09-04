"""Analysis View v0.1b Marco 2 — adversarial w:b / w:i tests.

Every helper path builds a synthetic DOCX, parses it through DocxParser v0.4,
builds the real StyleCatalog, and resolves a real PhysicalIR run.
"""
from __future__ import annotations

import io
import unittest
import zipfile

from formatador_academico.docx_parser import DocxParser
from formatador_academico.analysis.formatting import resolve_run_formatting
from formatador_academico.analysis.formatting_model import ResolutionStatus as RES
from formatador_academico.analysis.style_catalog import build_style_catalog

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
STYLES_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"


def _styles(inner: str) -> str:
    return f'<w:styles xmlns:w="{W}">{inner}</w:styles>'


def _doc(body: str) -> str:
    return f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{body}</w:body></w:document>'


def _pkg(body: str, styles: str | None = None) -> bytes:
    overrides = [f'<Override PartName="/word/document.xml" ContentType="{MAIN_CT}"/>']
    if styles is not None:
        overrides.append(f'<Override PartName="/word/styles.xml" ContentType="{STYLES_CT}"/>')
    ct = (f'<Types xmlns="{CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          f'<Default Extension="xml" ContentType="application/xml"/>{"".join(overrides)}</Types>')
    rels = f'<Relationships xmlns="{PR}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", _doc(body))
        if styles is not None:
            z.writestr("word/styles.xml", styles)
    return out.getvalue()


def _resolve(run_rpr: str = "", ppr: str = "", styles: str | None = None):
    body = f'<w:p><w:pPr>{ppr}</w:pPr><w:r><w:rPr>{run_rpr}</w:rPr><w:t>x</w:t></w:r></w:p>'
    package = _pkg(body, styles)
    ir = DocxParser().parse_bytes(package)
    assert ir["status"] == "ok", ir.get("errors")
    catalog = build_style_catalog(package, ir)
    p = ir["stories"][0]["blocks"][0]
    run = next(c for c in p["children"] if c["source_type"] == "run_raw")
    return resolve_run_formatting(run, p, catalog, "word/document.xml"), ir, package, catalog


def _pstyle(style_id: str) -> str:
    return f'<w:pStyle w:val="{style_id}"/>'


def _rstyle(style_id: str) -> str:
    return f'<w:rStyle w:val="{style_id}"/>'


class BoldToggleTests(unittest.TestCase):
    def test_01_absent_is_absent_not_false(self):
        fmt, *_ = _resolve()
        self.assertEqual(fmt.bold.status, RES.ABSENT)
        self.assertIsNone(fmt.bold.value)

    def test_02_docdefaults_on(self):
        s = _styles('<w:docDefaults><w:rPrDefault><w:rPr><w:b/></w:rPr></w:rPrDefault></w:docDefaults>')
        fmt, *_ = _resolve(styles=s)
        self.assertEqual((fmt.bold.status, fmt.bold.value), (RES.RESOLVED, True))

    def test_03_paragraph_style_on(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("P"), styles=s)
        self.assertTrue(fmt.bold.value)

    def test_04_parent_on_child_on_is_false(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="A"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("B"), styles=s)
        self.assertFalse(fmt.bold.value)

    def test_05_parent_on_child_false_is_true(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="A"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/><w:rPr><w:b w:val="false"/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("B"), styles=s)
        self.assertTrue(fmt.bold.value)

    def test_06_paragraph_and_character_on_is_false(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="character" w:styleId="C"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(run_rpr=_rstyle("C"), ppr=_pstyle("P"), styles=s)
        self.assertFalse(fmt.bold.value)
        self.assertIsNone(fmt.bold.winning_evidence)

    def test_07_character_false_is_noop(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="character" w:styleId="C"><w:rPr><w:b w:val="0"/></w:rPr></w:style>')
        fmt, *_ = _resolve(run_rpr=_rstyle("C"), ppr=_pstyle("P"), styles=s)
        self.assertTrue(fmt.bold.value)

    def test_08_docdefaults_plus_paragraph_on_is_false(self):
        s = _styles('<w:docDefaults><w:rPrDefault><w:rPr><w:b/></w:rPr></w:rPrDefault></w:docDefaults>'
                    '<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("P"), styles=s)
        self.assertFalse(fmt.bold.value)

    def test_09_three_style_layers_on_is_true(self):
        s = _styles('<w:docDefaults><w:rPrDefault><w:rPr><w:b/></w:rPr></w:rPrDefault></w:docDefaults>'
                    '<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="character" w:styleId="C"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(run_rpr=_rstyle("C"), ppr=_pstyle("P"), styles=s)
        self.assertTrue(fmt.bold.value)

    def test_10_style_on_direct_on_is_true_absolute(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(run_rpr='<w:b/>', ppr=_pstyle("P"), styles=s)
        self.assertTrue(fmt.bold.value)
        self.assertEqual(fmt.bold.evidence_chain[0].detail, "direct_true")

    def test_11_style_on_direct_false_is_false_absolute(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(run_rpr='<w:b w:val="off"/>', ppr=_pstyle("P"), styles=s)
        self.assertFalse(fmt.bold.value)

    def test_12_direct_true_without_styles(self):
        fmt, *_ = _resolve(run_rpr='<w:b w:val="true"/>')
        self.assertTrue(fmt.bold.value)

    def test_13_direct_false_without_styles(self):
        fmt, *_ = _resolve(run_rpr='<w:b w:val="false"/>')
        self.assertFalse(fmt.bold.value)

    def test_14_direct_invalid_is_invalid(self):
        fmt, *_ = _resolve(run_rpr='<w:b w:val="banana"/>')
        self.assertEqual(fmt.bold.status, RES.INVALID)
        self.assertIn("formatting_invalid_value", [w.code for w in fmt.analysis_warnings])

    def test_15_explicit_empty_val_is_invalid(self):
        fmt, *_ = _resolve(run_rpr='<w:b w:val=""/>')
        self.assertEqual(fmt.bold.status, RES.INVALID)

    def test_16_style_invalid_is_invalid(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b w:val="x"/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("P"), styles=s)
        self.assertEqual(fmt.bold.status, RES.INVALID)

    def test_17_direct_duplicate_equivalent_applied_once(self):
        fmt, *_ = _resolve(run_rpr='<w:b/><w:b w:val="1"/>')
        self.assertTrue(fmt.bold.value)
        self.assertIn("formatting_duplicate_property", [w.code for w in fmt.analysis_warnings])

    def test_18_direct_duplicate_conflict_is_ambiguous(self):
        fmt, *_ = _resolve(run_rpr='<w:b/><w:b w:val="0"/>')
        self.assertEqual(fmt.bold.status, RES.AMBIGUOUS)

    def test_19_style_duplicate_equivalent_toggles_once(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/><w:b w:val="on"/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("P"), styles=s)
        self.assertTrue(fmt.bold.value)

    def test_20_style_duplicate_conflict_is_ambiguous(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/><w:b w:val="false"/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("P"), styles=s)
        self.assertEqual(fmt.bold.status, RES.AMBIGUOUS)

    def test_21_three_basedon_on_is_true(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="A"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:styleId="C"><w:basedOn w:val="B"/><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("C"), styles=s)
        self.assertTrue(fmt.bold.value)

    def test_22_four_basedon_on_is_false(self):
        styles = []
        for ident, parent in (("A", None),("B","A"),("C","B"),("D","C")):
            based = "" if parent is None else f'<w:basedOn w:val="{parent}"/>'
            styles.append(f'<w:style w:type="paragraph" w:styleId="{ident}">{based}<w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("D"), styles=_styles("".join(styles)))
        self.assertFalse(fmt.bold.value)

    def test_23_cycle_without_direct_unresolved(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="A"><w:basedOn w:val="B"/><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("A"), styles=s)
        self.assertEqual((fmt.bold.status, fmt.bold.reason), (RES.UNRESOLVED, "style_cycle"))

    def test_24_cycle_with_direct_true_resolved(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="A"><w:basedOn w:val="B"/><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/></w:style>')
        fmt, *_ = _resolve(run_rpr='<w:b/>', ppr=_pstyle("A"), styles=s)
        self.assertEqual((fmt.bold.status, fmt.bold.value), (RES.RESOLVED, True))

    def test_25_missing_rstyle_does_not_block_paragraph(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(run_rpr=_rstyle("NOPE"), ppr=_pstyle("P"), styles=s)
        self.assertTrue(fmt.bold.value)
        self.assertIn("formatting_missing_style", [w.code for w in fmt.analysis_warnings])

    def test_26_wrong_type_rstyle_does_not_block_paragraph(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:styleId="C"/>')
        fmt, *_ = _resolve(run_rpr=_rstyle("C"), ppr=_pstyle("P"), styles=s)
        self.assertTrue(fmt.bold.value)

    def test_27_duplicate_style_id_first_definition(self):
        s = _styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:b w:val="false"/></w:rPr></w:style>')
        fmt, *_ = _resolve(ppr=_pstyle("P"), styles=s)
        self.assertTrue(fmt.bold.value)

    def test_28_multiple_default_paragraph_last_wins(self):
        s = _styles('<w:style w:type="paragraph" w:default="1" w:styleId="A"><w:rPr><w:b/></w:rPr></w:style>'
                    '<w:style w:type="paragraph" w:default="1" w:styleId="B"><w:rPr><w:b w:val="false"/></w:rPr></w:style>')
        fmt, *_ = _resolve(styles=s)
        self.assertFalse(fmt.bold.value)

    def test_29_default_without_style_id_applies(self):
        s = _styles('<w:style w:type="paragraph" w:default="1"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(styles=s)
        self.assertTrue(fmt.bold.value)

    def test_30_type_absent_defaults_paragraph(self):
        s = _styles('<w:style w:default="1"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(styles=s)
        self.assertTrue(fmt.bold.value)

    def test_31_absent_rstyle_does_not_apply_default_character(self):
        s = _styles('<w:style w:type="character" w:default="1" w:styleId="C"><w:rPr><w:b/></w:rPr></w:style>')
        fmt, *_ = _resolve(styles=s)
        self.assertEqual(fmt.bold.status, RES.ABSENT)


class ItalicToggleTests(unittest.TestCase):
    def test_01_absent(self):
        fmt, *_ = _resolve(); self.assertEqual(fmt.italic.status, RES.ABSENT)

    def test_02_docdefaults(self):
        s=_styles('<w:docDefaults><w:rPrDefault><w:rPr><w:i/></w:rPr></w:rPrDefault></w:docDefaults>')
        fmt,*_=_resolve(styles=s); self.assertTrue(fmt.italic.value)

    def test_03_parent_child_toggle(self):
        s=_styles('<w:style w:type="paragraph" w:styleId="A"><w:rPr><w:i/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/><w:rPr><w:i/></w:rPr></w:style>')
        fmt,*_=_resolve(ppr=_pstyle("B"),styles=s); self.assertFalse(fmt.italic.value)

    def test_04_paragraph_character(self):
        s=_styles('<w:style w:type="paragraph" w:styleId="P"><w:rPr><w:i/></w:rPr></w:style><w:style w:type="character" w:styleId="C"><w:rPr><w:i/></w:rPr></w:style>')
        fmt,*_=_resolve(run_rpr=_rstyle("C"),ppr=_pstyle("P"),styles=s); self.assertFalse(fmt.italic.value)

    def test_05_direct_true_absolute(self):
        fmt,*_=_resolve(run_rpr='<w:i/>'); self.assertTrue(fmt.italic.value)

    def test_06_direct_false_absolute(self):
        fmt,*_=_resolve(run_rpr='<w:i w:val="0"/>'); self.assertFalse(fmt.italic.value)

    def test_07_invalid(self):
        fmt,*_=_resolve(run_rpr='<w:i w:val="wat"/>'); self.assertEqual(fmt.italic.status,RES.INVALID)

    def test_08_duplicate_identical(self):
        fmt,*_=_resolve(run_rpr='<w:i/><w:i w:val="true"/>'); self.assertTrue(fmt.italic.value)

    def test_09_duplicate_conflict(self):
        fmt,*_=_resolve(run_rpr='<w:i/><w:i w:val="false"/>'); self.assertEqual(fmt.italic.status,RES.AMBIGUOUS)

    def test_10_cycle(self):
        s=_styles('<w:style w:type="paragraph" w:styleId="A"><w:basedOn w:val="B"/><w:rPr><w:i/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/></w:style>')
        fmt,*_=_resolve(ppr=_pstyle("A"),styles=s); self.assertEqual(fmt.italic.status,RES.UNRESOLVED)

    def test_11_direct_overrides_cycle(self):
        s=_styles('<w:style w:type="paragraph" w:styleId="A"><w:basedOn w:val="B"/><w:rPr><w:i/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/></w:style>')
        fmt,*_=_resolve(run_rpr='<w:i/>',ppr=_pstyle("A"),styles=s); self.assertTrue(fmt.italic.value)


class InvariantTests(unittest.TestCase):
    def test_physical_ir_and_package_not_mutated(self):
        fmt, ir, package, catalog = _resolve(run_rpr='<w:b/><w:i/>')
        before = repr(ir)
        package_before = bytes(package)
        self.assertTrue(fmt.bold.value and fmt.italic.value)
        self.assertEqual(repr(ir), before)
        self.assertEqual(package, package_before)
        self.assertEqual(catalog.part_status, "missing")


if __name__ == "__main__":
    unittest.main()
