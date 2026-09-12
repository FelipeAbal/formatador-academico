"""End-to-end — Analysis View v0.1b Marco 1.

DOCX sintético -> DocxParser v0.4 -> PhysicalIR REAL -> StyleCatalog
-> Formatting Resolution (paragraph + run), incluindo stories secundárias
(table cell, footnote, header, comment) e robustez de pacote.
"""

from __future__ import annotations

import copy
import unittest
from decimal import Decimal

from formatador_academico.docx_parser import DocxParser
from formatador_academico.analysis.formatting import (
    resolve_paragraph_formatting,
    resolve_run_formatting,
)
from formatador_academico.analysis.formatting_model import (
    ResolutionStatus as RES,
    serialize_resolved_paragraph,
    serialize_resolved_run,
)
from formatador_academico.analysis.style_catalog import build_style_catalog

from test_analysis_formatting_v01b_m1 import (
    build_docx,
    document,
    first_run,
    styles_part,
)

STYLES = styles_part(
    '<w:docDefaults>'
    '<w:rPrDefault><w:rPr><w:sz w:val="22"/><w:rFonts w:ascii="Arial"'
    ' w:asciiTheme="minorHAnsi"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="160"/></w:pPr></w:pPrDefault>'
    '</w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
    '<w:name w:val="Normal"/><w:pPr><w:jc w:val="both"/></w:pPr>'
    '<w:rPr><w:sz w:val="24"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Quote">'
    '<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/></w:pPr>'
    '<w:rPr><w:u w:val="single"/></w:rPr></w:style>'
    '<w:style w:type="character" w:styleId="Code">'
    '<w:rPr><w:rFonts w:ascii="Courier"/><w:vertAlign w:val="subscript"/></w:rPr></w:style>'
)


def parse_doc(body, styles=STYLES, extra_parts=None, story_rels=None):
    pkg = build_docx(document(body), styles, extra_parts, story_rels)
    ir = DocxParser().parse_bytes(pkg)
    assert ir["status"] == "ok", ir.get("errors")
    return pkg, ir, build_style_catalog(pkg, ir)


class FormattingV01bE2E(unittest.TestCase):
    def test_body_full_cascade(self):
        pkg, ir, cat = parse_doc(
            '<w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr>'
            '<w:r><w:rPr><w:rStyle w:val="Code"/><w:sz w:val="28"/></w:rPr>'
            '<w:t>abc</w:t></w:r></w:p>')
        p = ir["stories"][0]["blocks"][0]
        run = first_run(p)

        pf = resolve_paragraph_formatting(p, cat, "word/document.xml")
        self.assertEqual(pf.paragraph_style_id.value, "Quote")
        # jc from Normal via basedOn chain of Quote
        self.assertEqual(pf.alignment.status, RES.RESOLVED)
        self.assertEqual(pf.alignment.value, "both")
        self.assertEqual(pf.alignment.winning_evidence.style_id, "Normal")
        # indent from Quote
        self.assertEqual(pf.indents.left.value.value, Decimal("36"))
        # spacing after from docDefaults
        self.assertEqual(pf.spacing.after.value.value, Decimal("8"))

        rf = resolve_run_formatting(run, p, cat, "word/document.xml")
        # direct size wins over everything
        self.assertEqual(rf.font_size.value.value, Decimal("14"))
        self.assertEqual(rf.font_size.winning_evidence.source_kind, "direct")
        # font ascii from character style Code beats paragraph style/docDefaults
        self.assertEqual(rf.font_spec.ascii.value, "Courier")
        self.assertEqual(rf.font_spec.ascii.winning_evidence.style_id, "Code")
        # theme slot resolved as documental ThemeRef from docDefaults
        self.assertEqual(rf.font_spec.ascii_theme.status, RES.RESOLVED)
        self.assertEqual(rf.font_spec.ascii_theme.value.theme_slot, "minorHAnsi")
        # underline from paragraph style Quote rPr
        self.assertEqual(rf.underline.value, "single")
        self.assertEqual(rf.underline.winning_evidence.style_id, "Quote")
        # vertAlign from character style
        self.assertEqual(rf.vert_align.value, "subscript")

    def test_table_cell_paragraph(self):
        pkg, ir, cat = parse_doc(
            '<w:tbl><w:tr><w:tc>'
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="20"/></w:rPr><w:t>c</w:t></w:r></w:p>'
            '</w:tc></w:tr></w:tbl>')
        table = ir["stories"][0]["blocks"][0]
        cell = table["children"][0]["children"][0]
        p = next(b for b in cell["children"] if b["source_type"] == "paragraph")
        run = first_run(p)
        pf = resolve_paragraph_formatting(p, cat, "word/document.xml")
        self.assertEqual(pf.alignment.value, "center")
        self.assertIn("/w:tbl[1]/w:tr[1]/w:tc[1]/", pf.paragraph_path)
        rf = resolve_run_formatting(run, p, cat, "word/document.xml")
        self.assertEqual(rf.font_size.value.value, Decimal("10"))

    def test_footnote_paragraph(self):
        foot = ('<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:footnote w:id="2"><w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr>'
                '<w:r><w:t>n</w:t></w:r></w:p></w:footnote></w:footnotes>')
        pkg, ir, cat = parse_doc('<w:p><w:r><w:t>b</w:t></w:r></w:p>',
                                 extra_parts={"word/footnotes.xml": foot.encode()},
                                 story_rels=[("rF", "footnotes", "footnotes.xml")])
        story = next(s for s in ir["stories"] if s["story_type"] == "footnotes")
        p = story["items"][0]["blocks"][0]
        pf = resolve_paragraph_formatting(p, cat, story["part"])
        self.assertEqual(pf.alignment.value, "both")
        self.assertEqual(pf.indents.left.value.value, Decimal("36"))

    def test_header_paragraph(self):
        hdr = ('<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               '<w:p><w:pPr><w:jc w:val="right"/></w:pPr><w:r><w:t>h</w:t></w:r></w:p></w:hdr>')
        pkg, ir, cat = parse_doc('<w:p><w:r><w:t>b</w:t></w:r></w:p>',
                                 extra_parts={"word/header1.xml": hdr.encode()},
                                 story_rels=[("rH", "header", "header1.xml")])
        story = next(s for s in ir["stories"] if s["story_type"] == "header")
        p = story["blocks"][0]
        pf = resolve_paragraph_formatting(p, cat, story["part"])
        self.assertEqual(pf.alignment.value, "right")
        self.assertEqual(pf.alignment.winning_evidence.part, "word/header1.xml")

    def test_comment_paragraph(self):
        cmt = ('<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               '<w:comment w:id="7"><w:p><w:r><w:rPr><w:u w:val="double"/></w:rPr>'
               '<w:t>c</w:t></w:r></w:p></w:comment></w:comments>')
        pkg, ir, cat = parse_doc('<w:p><w:r><w:t>b</w:t></w:r></w:p>',
                                 extra_parts={"word/comments.xml": cmt.encode()},
                                 story_rels=[("rC", "comments", "comments.xml")])
        story = next(s for s in ir["stories"] if s["story_type"] == "comments")
        p = story["items"][0]["blocks"][0]
        run = first_run(p)
        rf = resolve_run_formatting(run, p, cat, story["part"])
        self.assertEqual(rf.underline.value, "double")
        self.assertEqual(rf.underline.winning_evidence.part, "word/comments.xml")

    def test_hyperlink_run_resolves_normally(self):
        pkg, ir, cat = parse_doc(
            '<w:p><w:hyperlink><w:r><w:rPr><w:rStyle w:val="Code"/></w:rPr>'
            '<w:t>h</w:t></w:r></w:hyperlink></w:p>')
        p = ir["stories"][0]["blocks"][0]
        container = p["children"][0]
        self.assertEqual(container["source_type"], "run_container")
        run = first_run(container)
        rf = resolve_run_formatting(run, p, cat, "word/document.xml")
        self.assertEqual(rf.font_spec.ascii.value, "Courier")
        self.assertIn("hyperlink", rf.run_path)

    def test_physical_ir_and_package_bytes_not_modified(self):
        pkg, ir, cat = parse_doc(
            '<w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="28"/></w:rPr><w:t>a</w:t></w:r></w:p>')
        before_ir = copy.deepcopy(ir)
        before_pkg = bytes(pkg)
        p = ir["stories"][0]["blocks"][0]
        run = first_run(p)
        resolve_paragraph_formatting(p, cat, "word/document.xml")
        resolve_run_formatting(run, p, cat, "word/document.xml")
        self.assertEqual(ir, before_ir)
        self.assertEqual(pkg, before_pkg)

    def test_serialization_roundtrip_json(self):
        import json
        _, ir, cat = parse_doc(
            '<w:p><w:r><w:rPr><w:sz w:val="28"/><w:rFonts w:asciiTheme="majorHAnsi"/></w:rPr>'
            '<w:t>a</w:t></w:r></w:p>')
        p = ir["stories"][0]["blocks"][0]
        run = first_run(p)
        rf = resolve_run_formatting(run, p, cat, "word/document.xml")
        data = json.loads(serialize_resolved_run(rf))
        self.assertEqual(data["font_size"]["value"]["value"], "14")  # Decimal as string
        self.assertEqual(data["font_size"]["status"], "resolved")
        self.assertEqual(data["font_spec"]["ascii_theme"]["value"]["theme_slot"], "majorHAnsi")
        pf = resolve_paragraph_formatting(p, cat, "word/document.xml")
        pdata = json.loads(serialize_resolved_paragraph(pf))
        # no pStyle -> default paragraph style Normal applies -> jc=both
        self.assertEqual(pdata["alignment"]["status"], "resolved")
        self.assertEqual(pdata["alignment"]["value"], "both")

    def test_styles_unreadable_partial_degradation(self):
        pkg = build_docx(document(
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="24"/></w:rPr><w:t>a</w:t></w:r></w:p>'),
            "<w:styles><oops")
        ir = DocxParser().parse_bytes(pkg)
        cat = build_style_catalog(pkg, ir)
        self.assertEqual(cat.part_status, "unreadable")
        p = ir["stories"][0]["blocks"][0]
        run = first_run(p)
        pf = resolve_paragraph_formatting(p, cat, "word/document.xml")
        # direct alignment survives; nothing else crashes
        self.assertEqual(pf.alignment.status, RES.RESOLVED)
        self.assertEqual(pf.spacing.before.status, RES.UNRESOLVED)
        self.assertEqual(pf.spacing.before.reason, "styles_unavailable")
        rf = resolve_run_formatting(run, p, cat, "word/document.xml")
        self.assertEqual(rf.font_size.status, RES.RESOLVED)
        self.assertEqual(rf.underline.status, RES.UNRESOLVED)


if __name__ == "__main__":
    unittest.main()
