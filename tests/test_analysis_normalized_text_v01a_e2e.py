"""End-to-end: DOCX sintetico -> DocxParser v0.4 -> PhysicalIR REAL -> normalize_paragraph.

Cobre os 15 cenarios obrigatorios da auditoria adversarial v0.1a e as
regressoes dos achados E/J (opacos silenciosos) e F (break type desconhecido).
"""
from __future__ import annotations

import copy
import io
import unittest
import zipfile

from lxml import etree

from formatador_academico.analysis import (
    SegmentKind,
    TextRole,
    normalize_paragraph,
)
from formatador_academico.docx_parser import DocxParser

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL = R + "/officeDocument"
RELBASE = R + "/"
MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
STORY_CTS = {
    "footnotes": "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
    "header": "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
    "comments": "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
}


def qn(ns, t):
    return f"{{{ns}}}{t}"


def frag(tag, text=None, attrs=None):
    e = etree.Element(qn(W, tag), attrs or {})
    e.text = text
    return e


def run(*children):
    r = etree.Element(qn(W, "r"))
    for c in children:
        r.append(c)
    return r


def para(*children):
    p = etree.Element(qn(W, "p"))
    for c in children:
        p.append(c)
    return p


def table_with(cell_paragraph):
    tbl = etree.Element(qn(W, "tbl"))
    tr = etree.SubElement(tbl, qn(W, "tr"))
    tc = etree.SubElement(tr, qn(W, "tc"))
    tc.append(cell_paragraph)
    return tbl


def document(children):
    root = etree.Element(qn(W, "document"), nsmap={"w": W, "r": R})
    body = etree.SubElement(root, qn(W, "body"))
    for c in children:
        body.append(c)
    body.append(etree.Element(qn(W, "sectPr")))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def story_part(root_tag, child_tag, items):
    root = etree.Element(qn(W, root_tag), nsmap={"w": W})
    for item_id, blocks in items:
        item = etree.SubElement(root, qn(W, child_tag), {qn(W, "id"): item_id})
        for b in blocks:
            item.append(b)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def header_part(paragraphs):
    root = etree.Element(qn(W, "hdr"), nsmap={"w": W})
    for p in paragraphs:
        root.append(p)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def build_docx(doc, extra_parts=None, story_rels=None):
    extra_parts = extra_parts or {}
    story_rels = story_rels or []

    ct = etree.Element(qn(CT, "Types"), nsmap={None: CT})
    etree.SubElement(ct, qn(CT, "Default"), Extension="rels",
                     ContentType="application/vnd.openxmlformats-package.relationships+xml")
    etree.SubElement(ct, qn(CT, "Default"), Extension="xml", ContentType="application/xml")
    etree.SubElement(ct, qn(CT, "Override"), PartName="/word/document.xml", ContentType=MAIN_CT)
    for name, ctype in extra_parts.items():
        etree.SubElement(ct, qn(CT, "Override"), PartName="/" + name, ContentType=ctype)

    root_rels = etree.Element(qn(PR, "Relationships"), nsmap={None: PR})
    etree.SubElement(root_rels, qn(PR, "Relationship"), Id="rId1", Type=OFFICE_REL,
                     Target="word/document.xml")

    doc_rels = etree.Element(qn(PR, "Relationships"), nsmap={None: PR})
    for rid, stype, target in story_rels:
        etree.SubElement(doc_rels, qn(PR, "Relationship"), Id=rid,
                         Type=RELBASE + stype, Target=target)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", etree.tostring(ct, xml_declaration=True, encoding="UTF-8"))
        z.writestr("_rels/.rels", etree.tostring(root_rels, xml_declaration=True, encoding="UTF-8"))
        z.writestr("word/document.xml", doc)
        if story_rels:
            z.writestr("word/_rels/document.xml.rels",
                       etree.tostring(doc_rels, xml_declaration=True, encoding="UTF-8"))
        for name, data in extra_parts.items():
            z.writestr(name, data)
    return buf.getvalue()


class NormalizedTextV01aE2E(unittest.TestCase):
    """DOCX sintetico -> DocxParser v0.4 -> PhysicalIR REAL -> normalize_paragraph."""

    def setUp(self):
        self.parser = DocxParser()

    def parse_body(self, *blocks):
        result = self.parser.parse_bytes(build_docx(document(list(blocks))))
        self.assertEqual(result["status"], "ok")
        return result, result["stories"][0]

    def story(self, result, story_type):
        return [s for s in result["stories"] if s["story_type"] == story_type][0]

    def normalize_block_paragraph(self, story, index=0):
        p = story["blocks"][index]
        self.assertEqual(p["source_type"], "paragraph")
        return normalize_paragraph(p, story["story_id"], story["part"])

    # 1. palavra fragmentada em runs
    def test_e2e_01_split_word_across_runs(self):
        _, story = self.parse_body(para(
            run(frag("t", "Com")), run(frag("t", "pra")),
            run(frag("t", " sem")), run(frag("t", "ântica")),
        ))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(r.default_text, "Compra semântica")
        self.assertEqual(len(r.segments), 4)
        self.assertTrue(all(s.segment_kind is SegmentKind.TEXT for s in r.segments))

    # 2. hyperlink (run_container real)
    def test_e2e_02_hyperlink(self):
        hl = etree.Element(qn(W, "hyperlink"))
        hl.append(run(frag("t", "click ")))
        hl.append(run(frag("t", "here")))
        _, story = self.parse_body(para(hl))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(r.default_text, "click here")
        self.assertEqual(len(r.segments), 2)
        self.assertIn("hyperlink", r.segments[0].source.structural_path)

    # 3. line break (sem type e com textWrapping explicito)
    def test_e2e_03_line_break(self):
        _, story = self.parse_body(para(run(
            frag("t", "a"), frag("br"), frag("br", attrs={qn(W, "type"): "textWrapping"}), frag("t", "b"),
        )))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(r.default_text, "a\n\nb")
        kinds = [s.segment_kind for s in r.segments]
        self.assertEqual(kinds, [SegmentKind.TEXT, SegmentKind.LINE_BREAK,
                                 SegmentKind.LINE_BREAK, SegmentKind.TEXT])

    # 4. page break -> zero-width estrutural
    def test_e2e_04_page_break(self):
        _, story = self.parse_body(para(run(frag("t", "a")), run(frag("br", attrs={qn(W, "type"): "page"})), run(frag("t", "b"))))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(r.default_text, "ab")
        s = r.segments[1]
        self.assertEqual(s.segment_kind, SegmentKind.PAGE_BREAK)
        self.assertEqual(s.text_role, TextRole.STRUCTURAL)
        self.assertEqual((s.logical_start, s.logical_end), (1, 1))
        self.assertIsNone(s.projected_text)

    # 5. column break -> zero-width estrutural
    def test_e2e_05_column_break(self):
        _, story = self.parse_body(para(run(frag("br", attrs={qn(W, "type"): "column"}))))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(r.segments[0].segment_kind, SegmentKind.COLUMN_BREAK)
        self.assertEqual(r.default_text, "")

    # 6. instrText -> FIELD_CODE zero-width, fora de default_text
    def test_e2e_06_instruction_text(self):
        _, story = self.parse_body(para(run(
            frag("t", "a"), frag("instrText", " PAGE "), frag("t", "b"),
        )))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(r.default_text, "ab")
        s = r.segments[1]
        self.assertEqual(s.segment_kind, SegmentKind.FIELD_CODE)
        self.assertEqual(s.text_role, TextRole.FIELD_INTERNAL)
        self.assertEqual(s.raw_text, " PAGE ")
        self.assertEqual((s.logical_start, s.logical_end), (1, 1))

    # 7. delText / tracked deletion via container w:del real
    def test_e2e_07_tracked_deletion(self):
        d = etree.Element(qn(W, "del"))
        d.append(run(frag("delText", "removido")))
        _, story = self.parse_body(para(run(frag("t", "a")), d, run(frag("t", "b"))))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(r.default_text, "ab")
        kinds = [s.segment_kind for s in r.segments]
        self.assertEqual(kinds, [SegmentKind.TEXT, SegmentKind.DELETED_TEXT, SegmentKind.TEXT])
        self.assertEqual(r.segments[1].raw_text, "removido")
        self.assertEqual(r.segments[1].text_role, TextRole.DELETED)

    # 8. symbol -> cru em metadata, zero-width, sem U+FFFD
    def test_e2e_08_symbol(self):
        _, story = self.parse_body(para(run(
            frag("sym", attrs={qn(W, "font"): "Wingdings", qn(W, "char"): "F0A7"}),
        )))
        r = self.normalize_block_paragraph(story)
        s = r.segments[0]
        self.assertEqual(s.segment_kind, SegmentKind.SYMBOL)
        self.assertEqual(dict(s.metadata), {"font": "Wingdings", "char": "F0A7"})
        self.assertEqual(r.default_text, "")
        self.assertNotIn("\ufffd", serialize_all(r))

    # 9. opaque entre textos (w:bookmarkStart real vira opaque_paragraph_child)
    def test_e2e_09_opaque_between_texts(self):
        _, story = self.parse_body(para(
            run(frag("t", "antes")),
            frag("bookmarkStart", attrs={qn(W, "id"): "1", qn(W, "name"): "bm"}),
            run(frag("t", "depois")),
        ))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(r.default_text, "antesdepois")
        kinds = [s.segment_kind for s in r.segments]
        self.assertEqual(kinds, [SegmentKind.TEXT, SegmentKind.OPAQUE, SegmentKind.TEXT])
        op = r.segments[1]
        self.assertEqual((op.logical_start, op.logical_end), (5, 5))
        self.assertEqual(op.text_role, TextRole.OPAQUE)
        self.assertIn("bookmarkStart", op.source.structural_path)

    # 10. table cell
    def test_e2e_10_table_cell(self):
        _, story = self.parse_body(table_with(para(run(frag("t", "cell")))))
        table = story["blocks"][0]
        self.assertEqual(table["source_type"], "table")
        cell = table["children"][0]["children"][0]
        p = cell["children"][0]
        self.assertEqual(p["source_type"], "paragraph")
        r = normalize_paragraph(p, story["story_id"], story["part"])
        self.assertEqual(r.default_text, "cell")
        self.assertIn("/w:tbl[1]/w:tr[1]/w:tc[1]/", r.paragraph_path)

    # 11. footnote
    def test_e2e_11_footnote(self):
        part = "word/footnotes.xml"
        data = story_part("footnotes", "footnote", [("2", [para(run(frag("t", "nota")))])])
        result = self.parser.parse_bytes(build_docx(
            document([para(run(frag("t", "corpo")))]),
            {part: data}, [("rF", "footnotes", "footnotes.xml")],
        ))
        self.assertEqual(result["status"], "ok")
        s = self.story(result, "footnotes")
        p = s["items"][0]["blocks"][0]
        r = normalize_paragraph(p, s["story_id"], s["part"])
        self.assertEqual(r.default_text, "nota")
        self.assertEqual(r.segments[0].source.story_id, s["story_id"])
        self.assertEqual(r.segments[0].source.part, "word/footnotes.xml")

    # 12. header
    def test_e2e_12_header(self):
        part = "word/header1.xml"
        data = header_part([para(run(frag("t", "cabecalho")))])
        result = self.parser.parse_bytes(build_docx(
            document([para(run(frag("t", "corpo")))]),
            {part: data}, [("rH", "header", "header1.xml")],
        ))
        self.assertEqual(result["status"], "ok")
        s = self.story(result, "header")
        r = normalize_paragraph(s["blocks"][0], s["story_id"], s["part"])
        self.assertEqual(r.default_text, "cabecalho")
        self.assertEqual(r.segments[0].source.part, "word/header1.xml")

    # 13. comment
    def test_e2e_13_comment(self):
        part = "word/comments.xml"
        data = story_part("comments", "comment", [("7", [para(run(frag("t", "comentario")))])])
        result = self.parser.parse_bytes(build_docx(
            document([para(run(frag("t", "corpo")))]),
            {part: data}, [("rC", "comments", "comments.xml")],
        ))
        self.assertEqual(result["status"], "ok")
        s = self.story(result, "comments")
        p = s["items"][0]["blocks"][0]
        r = normalize_paragraph(p, s["story_id"], s["part"])
        self.assertEqual(r.default_text, "comentario")

    # 14. combining mark: offsets em code points
    def test_e2e_14_combining_mark(self):
        _, story = self.parse_body(para(run(frag("t", "e\u0301"))))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(len(r.default_text), 2)
        self.assertEqual((r.segments[0].logical_start, r.segments[0].logical_end), (0, 2))
        self.assertEqual((r.segments[0].source.source_start, r.segments[0].source.source_end), (0, 2))

    # 15. emoji fora do BMP conta como um code point
    def test_e2e_15_emoji_outside_bmp(self):
        _, story = self.parse_body(para(run(frag("t", "\U0001F600"))))
        r = self.normalize_block_paragraph(story)
        self.assertEqual(len(r.default_text), 1)
        self.assertEqual(r.segments[0].source.source_end, 1)

    # Regressao E: opaque_paragraph_child nunca some entre textos
    def test_regression_opaque_paragraph_child_not_dropped(self):
        _, story = self.parse_body(para(
            run(frag("t", "a")),
            frag("bookmarkEnd", attrs={qn(W, "id"): "1"}),
            run(frag("t", "b")),
        ))
        p = story["blocks"][0]
        self.assertEqual(p["children"][1]["source_type"], "opaque_paragraph_child")
        r = self.normalize_block_paragraph(story)
        self.assertEqual([s.segment_kind for s in r.segments],
                         [SegmentKind.TEXT, SegmentKind.OPAQUE, SegmentKind.TEXT])

    # Regressao J: opaque_container_child dentro de run_container nao some
    def test_regression_opaque_container_child_not_dropped(self):
        hl = etree.Element(qn(W, "hyperlink"))
        hl.append(run(frag("t", "a")))
        hl.append(frag("proofErr", attrs={qn(W, "type"): "gramStart"}))
        hl.append(run(frag("t", "b")))
        _, story = self.parse_body(para(hl))
        container = story["blocks"][0]["children"][0]
        self.assertEqual(container["source_type"], "run_container")
        self.assertEqual(container["children"][1]["source_type"], "opaque_container_child")
        r = self.normalize_block_paragraph(story)
        self.assertEqual([s.segment_kind for s in r.segments],
                         [SegmentKind.TEXT, SegmentKind.OPAQUE, SegmentKind.TEXT])
        self.assertEqual(r.default_text, "ab")

    # Regressao F: w:type desconhecido NUNCA vira LINE_BREAK silencioso
    def test_regression_unknown_break_type_is_opaque_with_warning(self):
        _, story = self.parse_body(para(run(
            frag("t", "a"), frag("br", attrs={qn(W, "type"): "continuous"}), frag("t", "b"),
        )))
        r = self.normalize_block_paragraph(story)
        s = r.segments[1]
        self.assertEqual(s.segment_kind, SegmentKind.OPAQUE)
        self.assertFalse(s.contributes_to_default_text)
        self.assertEqual((s.logical_start, s.logical_end), (1, 1))
        self.assertEqual(r.default_text, "ab")
        self.assertIn("normalized_unknown_break_type", [w.code for w in r.analysis_warnings])

    # PhysicalIR real nao e modificada pela normalizacao
    def test_e2e_physical_ir_not_modified(self):
        result, story = self.parse_body(para(run(
            frag("t", "a"), frag("br", attrs={qn(W, "type"): "page"}), frag("instrText", " X "),
        )))
        before = copy.deepcopy(result)
        self.normalize_block_paragraph(story)
        self.assertEqual(result, before)


def serialize_all(paragraph) -> str:
    from formatador_academico.analysis import normalized_paragraph_to_json
    return normalized_paragraph_to_json(paragraph)


if __name__ == "__main__":
    unittest.main()
