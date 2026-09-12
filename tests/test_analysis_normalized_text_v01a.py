from __future__ import annotations

import copy
import unittest

from formatador_academico.analysis import (
    SegmentKind,
    TextRole,
    normalize_paragraph,
    normalized_paragraph_to_json,
    serialize_normalized_paragraph,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def fragment(ft="text", text=None, path="/w:p[1]/w:r[1]/w:t[1]", *, source_type="text_fragment", xml=None, symbol=None):
    rec = {
        "source_type": source_type,
        "structural_path": path,
        "physical_hash": "h:" + path,
        "canonical_xml": xml or f'<w:t xmlns:w="{W}"></w:t>',
    }
    if ft is not None:
        rec["fragment_type"] = ft
    if text is not None:
        rec["text"] = text
    if symbol is not None:
        rec["symbol"] = symbol
    return rec


def run(*children, path="/w:p[1]/w:r[1]"):
    return {"source_type": "run_raw", "structural_path": path, "physical_hash": "run:" + path, "children": list(children)}


def container(*children, path="/w:p[1]/w:hyperlink[1]", kind="hyperlink"):
    return {"source_type": "run_container", "container_type": kind, "structural_path": path, "physical_hash": "container:" + path, "children": list(children)}


def paragraph(*children, path="/w:p[1]"):
    return {"source_type": "paragraph", "structural_path": path, "physical_hash": "p:" + path, "children": list(children)}


def norm(p):
    return normalize_paragraph(p, "body", "word/document.xml")


class NormalizedTextV01aTests(unittest.TestCase):
    def test_01_one_run_one_text(self):
        r = norm(paragraph(run(fragment("text", "Hello"))))
        self.assertEqual(r.default_text, "Hello")
        self.assertEqual(r.segments[0].segment_kind, SegmentKind.TEXT)
        self.assertEqual((r.segments[0].logical_start, r.segments[0].logical_end), (0, 5))

    def test_02_split_word_across_runs(self):
        p = paragraph(
            run(fragment("text", "Com", "/p/r1/t")),
            run(fragment("text", "pra", "/p/r2/t")),
            run(fragment("text", " sem", "/p/r3/t")),
            run(fragment("text", "ântica", "/p/r4/t")),
        )
        r = norm(p)
        self.assertEqual(r.default_text, "Compra semântica")
        self.assertEqual(len(r.segments), 4)

    def test_03_empty_run(self):
        r = norm(paragraph(run()))
        self.assertEqual(r.segments, ())
        self.assertEqual(r.default_text, "")

    def test_04_empty_paragraph(self):
        r = norm(paragraph())
        self.assertEqual(r.segments, ())
        self.assertEqual(r.default_text, "")
        self.assertFalse(r.has_non_content)

    def test_05_hyperlink_multiple_runs(self):
        c = container(
            run(fragment("text", "click ", "/p/h/r1/t")),
            run(fragment("text", "here", "/p/h/r2/t")),
        )
        r = norm(paragraph(c))
        self.assertEqual(r.default_text, "click here")
        self.assertIn("/p/h/", r.segments[0].source.structural_path)

    def test_06_nested_run_containers(self):
        inner = container(run(fragment("text", "nested", "/p/sdt/content/r/t")), path="/p/sdt/content", kind="sdtContent")
        outer = container(inner, path="/p/sdt", kind="sdt")
        self.assertEqual(norm(paragraph(outer)).default_text, "nested")

    def test_07_tab(self):
        r = norm(paragraph(run(fragment("tab", path="/p/r/tab"))))
        self.assertEqual(r.default_text, "\t")
        self.assertEqual(r.segments[0].segment_kind, SegmentKind.TAB)

    def test_08_line_break(self):
        xml = f'<w:br xmlns:w="{W}"></w:br>'
        r = norm(paragraph(run(fragment("break", path="/p/r/br", xml=xml))))
        self.assertEqual(r.default_text, "\n")
        self.assertEqual(r.segments[0].segment_kind, SegmentKind.LINE_BREAK)

    def test_09_page_break_zero_width(self):
        xml = f'<w:br xmlns:w="{W}" w:type="page"></w:br>'
        r = norm(paragraph(run(fragment("break", path="/p/r/br", xml=xml))))
        s = r.segments[0]
        self.assertEqual(s.segment_kind, SegmentKind.PAGE_BREAK)
        self.assertEqual((s.logical_start, s.logical_end), (0, 0))
        self.assertEqual(r.default_text, "")

    def test_10_column_break_zero_width(self):
        xml = f'<w:br xmlns:w="{W}" w:type="column"></w:br>'
        r = norm(paragraph(run(fragment("break", path="/p/r/br", xml=xml))))
        self.assertEqual(r.segments[0].segment_kind, SegmentKind.COLUMN_BREAK)
        self.assertEqual(r.default_text, "")

    def test_11_carriage_return(self):
        r = norm(paragraph(run(fragment("carriage_return", path="/p/r/cr"))))
        self.assertEqual(r.default_text, "\r")

    def test_12_soft_hyphen(self):
        r = norm(paragraph(run(fragment("soft_hyphen", path="/p/r/sh"))))
        self.assertEqual(r.default_text, "\u00ad")

    def test_13_no_break_hyphen(self):
        r = norm(paragraph(run(fragment("no_break_hyphen", path="/p/r/nbh"))))
        self.assertEqual(r.default_text, "\u2011")

    def test_14_field_code_between_content(self):
        p = paragraph(run(
            fragment("text", "a", "/a"),
            fragment("instruction_text", " PAGE ", "/field"),
            fragment("text", "b", "/b"),
        ))
        r = norm(p)
        self.assertEqual(r.default_text, "ab")
        s = r.segments[1]
        self.assertEqual(s.segment_kind, SegmentKind.FIELD_CODE)
        self.assertEqual(s.text_role, TextRole.FIELD_INTERNAL)
        self.assertEqual(s.raw_text, " PAGE ")
        self.assertEqual((s.logical_start, s.logical_end), (1, 1))

    def test_15_deleted_text_between_content(self):
        p = paragraph(run(fragment("text", "a", "/a"), fragment("deleted_text", "x", "/d"), fragment("text", "b", "/b")))
        r = norm(p)
        self.assertEqual(r.default_text, "ab")
        self.assertEqual(r.segments[1].segment_kind, SegmentKind.DELETED_TEXT)
        self.assertEqual(r.segments[1].raw_text, "x")

    def test_16_opaque_fragment_between_content(self):
        op = fragment(None, path="/opaque", source_type="opaque_fragment")
        p = paragraph(run(fragment("text", "a", "/a"), op, fragment("text", "b", "/b")))
        r = norm(p)
        self.assertEqual(r.default_text, "ab")
        self.assertEqual(r.segments[1].segment_kind, SegmentKind.OPAQUE)

    def test_17_two_zero_width_consecutive(self):
        p = paragraph(run(fragment("instruction_text", "F1", "/f1"), fragment("deleted_text", "F2", "/f2")))
        r = norm(p)
        self.assertEqual([(s.logical_start, s.logical_end) for s in r.segments], [(0, 0), (0, 0)])

    def test_18_symbol_unresolved_metadata(self):
        r = norm(paragraph(run(fragment("symbol", path="/sym", symbol={"font": "Wingdings", "char": "F0A7"}))))
        s = r.segments[0]
        self.assertEqual(s.segment_kind, SegmentKind.SYMBOL)
        self.assertEqual(dict(s.metadata), {"font": "Wingdings", "char": "F0A7"})
        self.assertIsNone(s.projected_text)
        self.assertEqual(r.default_text, "")

    def test_19_combining_mark_offsets(self):
        r = norm(paragraph(run(fragment("text", "e\u0301"))))
        self.assertEqual(len(r.default_text), 2)
        self.assertEqual(r.segments[0].source.source_end, 2)
        self.assertEqual(r.segments[0].logical_end, 2)

    def test_20_emoji_outside_bmp_one_codepoint(self):
        r = norm(paragraph(run(fragment("text", "😀"))))
        self.assertEqual(len(r.default_text), 1)
        self.assertEqual(r.segments[0].source.source_end, 1)

    def test_21_table_cell_path_is_preserved(self):
        path = "/w:document/w:body[1]/w:tbl[1]/w:tr[1]/w:tc[1]/w:p[1]/w:r[1]/w:t[1]"
        r = norm(paragraph(run(fragment("text", "cell", path)), path="/w:document/w:body[1]/w:tbl[1]/w:tr[1]/w:tc[1]/w:p[1]"))
        self.assertIn("/w:tbl[1]/w:tr[1]/w:tc[1]/", r.segments[0].source.structural_path)

    def test_22_footnote_anchor_context_is_external_input(self):
        p = paragraph(run(fragment("text", "note", "/w:footnotes/w:footnote/p/r/t")), path="/w:footnotes/w:footnote/p")
        r = normalize_paragraph(p, "footnotes:word/footnotes.xml", "word/footnotes.xml")
        self.assertEqual(r.segments[0].source.story_id, "footnotes:word/footnotes.xml")
        self.assertEqual(r.segments[0].source.part, "word/footnotes.xml")

    def test_23_header_anchor_context(self):
        p = paragraph(run(fragment("text", "h", "/w:hdr/p/r/t")), path="/w:hdr/p")
        r = normalize_paragraph(p, "header:word/header1.xml", "word/header1.xml")
        self.assertEqual(r.segments[0].source.part, "word/header1.xml")

    def test_24_comment_anchor_context(self):
        p = paragraph(run(fragment("text", "c", "/w:comments/comment/p/r/t")), path="/w:comments/comment/p")
        r = normalize_paragraph(p, "comments:word/comments.xml", "word/comments.xml")
        self.assertEqual(r.default_text, "c")

    def test_25_determinism_same_input(self):
        p = paragraph(run(fragment("text", "abc")))
        self.assertEqual(serialize_normalized_paragraph(norm(p)), serialize_normalized_paragraph(norm(p)))

    def test_26_physical_ir_not_modified(self):
        p = paragraph(run(fragment("text", "abc")))
        before = copy.deepcopy(p)
        norm(p)
        self.assertEqual(p, before)

    def test_27_source_anchor_matches_fragment(self):
        f = fragment("text", "abc", "/exact/path")
        r = norm(paragraph(run(f)))
        self.assertEqual(r.segments[0].source.structural_path, f["structural_path"])
        self.assertEqual(r.segments[0].source.physical_hash, f["physical_hash"])

    def test_28_offsets_monotonic(self):
        p = paragraph(run(fragment("text", "a", "/1"), fragment("instruction_text", "X", "/2"), fragment("text", "bc", "/3")))
        r = norm(p)
        self.assertEqual([(s.logical_start, s.logical_end) for s in r.segments], [(0, 1), (1, 1), (1, 3)])

    def test_29_participants_are_contiguous(self):
        p = paragraph(run(fragment("text", "a", "/1"), fragment("tab", path="/2"), fragment("text", "b", "/3")))
        r = norm(p)
        parts = [s for s in r.segments if s.contributes_to_default_text]
        for left, right in zip(parts, parts[1:]):
            self.assertEqual(left.logical_end, right.logical_start)

    def test_30_projection_concat_equals_default_text(self):
        p = paragraph(run(fragment("text", "a", "/1"), fragment("deleted_text", "X", "/2"), fragment("tab", path="/3"), fragment("text", "b", "/4")))
        r = norm(p)
        projected = "".join(s.projected_text for s in r.segments if s.contributes_to_default_text)
        self.assertEqual(projected, r.default_text)

    def test_31_unknown_fragment_warns_and_becomes_opaque(self):
        r = norm(paragraph(run(fragment("future_kind", "x", "/future"))))
        self.assertEqual(r.default_text, "")
        self.assertEqual(r.segments[0].segment_kind, SegmentKind.OPAQUE)
        self.assertEqual(r.analysis_warnings[0].code, "normalized_unexpected_fragment")

    def test_32_serialization_is_exact_bytes(self):
        r = norm(paragraph(run(fragment("text", "á"))))
        a = serialize_normalized_paragraph(r)
        b = serialize_normalized_paragraph(r)
        self.assertIsInstance(a, bytes)
        self.assertEqual(a, b)
        self.assertIn("á", normalized_paragraph_to_json(r))

    def test_33_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            normalize_paragraph({"source_type": "table"}, "body", "word/document.xml")


if __name__ == "__main__":
    unittest.main()
