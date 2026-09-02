from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from formatador_academico.docx_parser import DocxParser, serialize_parse_result  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"


def qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def make_document(children: list[etree._Element]) -> bytes:
    root = etree.Element(qn(W, "document"), nsmap={"w": W, "r": R})
    body = etree.SubElement(root, qn(W, "body"))
    for child in children:
        body.append(child)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def paragraph(text: str) -> etree._Element:
    p = etree.Element(qn(W, "p"))
    r = etree.SubElement(p, qn(W, "r"))
    t = etree.SubElement(r, qn(W, "t"))
    t.text = text
    return p


def table() -> etree._Element:
    tbl = etree.Element(qn(W, "tbl"))
    tr = etree.SubElement(tbl, qn(W, "tr"))
    tc = etree.SubElement(tr, qn(W, "tc"))
    tc.append(paragraph("cell"))
    return tbl


def sectpr() -> etree._Element:
    node = etree.Element(qn(W, "sectPr"))
    etree.SubElement(node, qn(W, "pgSz"), {qn(W, "w"): "11906", qn(W, "h"): "16838"})
    return node


def content_types() -> bytes:
    root = etree.Element(qn(CT, "Types"), nsmap={None: CT})
    etree.SubElement(root, qn(CT, "Default"), Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    etree.SubElement(root, qn(CT, "Default"), Extension="xml", ContentType="application/xml")
    etree.SubElement(root, qn(CT, "Override"), PartName="/word/document.xml", ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def package_rels() -> bytes:
    root = etree.Element(qn(PR, "Relationships"), nsmap={None: PR})
    etree.SubElement(root, qn(PR, "Relationship"), Id="rId1", Type=OFFICE_REL, Target="word/document.xml")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def build_docx(document_xml: bytes, *, extra_parts: dict[str, bytes] | None = None, timestamp=(2026, 1, 1, 0, 0, 0)) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        parts = {"[Content_Types].xml": content_types(), "_rels/.rels": package_rels(), "word/document.xml": document_xml}
        if extra_parts:
            parts.update(extra_parts)
        for name, data in parts.items():
            info = zipfile.ZipInfo(name, timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return buf.getvalue()


class ParserV01Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = DocxParser()

    def test_determinism_same_input(self):
        data = build_docx(make_document([paragraph("A"), paragraph("B"), sectpr()]))
        self.assertEqual(serialize_parse_result(self.parser.parse_bytes(data)), serialize_parse_result(self.parser.parse_bytes(data)))

    def test_minimal_document_counts_types_paths_and_indices(self):
        data = build_docx(make_document([paragraph("A"), paragraph("B"), table(), sectpr()]))
        result = self.parser.parse_bytes(data)
        self.assertEqual(result["status"], "ok")
        blocks = result["stories"][0]["blocks"]
        self.assertEqual([b["source_type"] for b in blocks], ["paragraph", "paragraph", "table", "section_properties"])
        self.assertEqual([b["original_index"] for b in blocks], [0, 1, 2, 3])
        self.assertEqual(blocks[0]["structural_path"], "/w:document/w:body[1]/w:p[1]")
        self.assertEqual(blocks[1]["structural_path"], "/w:document/w:body[1]/w:p[2]")
        self.assertEqual(blocks[2]["structural_path"], "/w:document/w:body[1]/w:tbl[1]")
        self.assertEqual(blocks[3]["structural_path"], "/w:document/w:body[1]/w:sectPr[1]")
        self.assertTrue(all(b["raw_xml"] for b in blocks))
        self.assertTrue(blocks[3]["protected"])
        self.assertIn("unparsed_children", [w["code"] for w in result["parse_warnings"]])

    def test_opaque_body_child_is_preserved_warned_and_protected(self):
        sdt = etree.Element(qn(W, "sdt"))
        content = etree.SubElement(sdt, qn(W, "sdtContent"))
        content.append(paragraph("inside"))
        data = build_docx(make_document([paragraph("A"), sdt, sectpr()]))
        result = self.parser.parse_bytes(data)
        block = result["stories"][0]["blocks"][1]
        self.assertEqual(block["source_type"], "opaque_object")
        self.assertTrue(block["protected"])
        self.assertIn("sdt", block["raw_xml"])
        self.assertIn("unsupported_body_child", [w["code"] for w in result["parse_warnings"]])

    def test_direct_body_children_have_exact_one_to_one_block_coverage(self):
        doc_xml = make_document([paragraph("A"), table(), paragraph("B"), sectpr()])
        result = self.parser.parse_bytes(build_docx(doc_xml))
        root = etree.fromstring(doc_xml)
        body = root.find(qn(W, "body"))
        blocks = result["stories"][0]["blocks"]
        self.assertEqual(len(list(body)), len(blocks))
        self.assertEqual(len({b["id"] for b in blocks}), len(blocks))
        canonical_original = [etree.tostring(child, method="c14n", exclusive=False, with_comments=True).decode("utf-8") for child in body]
        self.assertEqual(canonical_original, [b["raw_xml"] for b in blocks])

    def test_failures_are_controlled(self):
        not_zip = self.parser.parse_bytes(b"not a zip")
        self.assertEqual(not_zip["status"], "failed")
        self.assertEqual(not_zip["parse_warnings"][0]["code"], "not_a_docx")
        self.assertEqual(not_zip["stories"], [])

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("[Content_Types].xml", content_types())
        missing = self.parser.parse_bytes(buf.getvalue())
        self.assertEqual(missing["status"], "failed")
        self.assertEqual(missing["parse_warnings"][0]["code"], "missing_document_xml")

        malformed = build_docx(b"<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>")
        malformed_result = self.parser.parse_bytes(malformed)
        self.assertEqual(malformed_result["status"], "failed")
        self.assertEqual(malformed_result["parse_warnings"][0]["code"], "malformed_xml")

    def test_block_physical_hash_ignores_zip_timestamp_packaging_difference(self):
        document = make_document([paragraph("Same"), sectpr()])
        a = build_docx(document, timestamp=(2025, 1, 1, 0, 0, 0))
        b = build_docx(document, timestamp=(2026, 1, 1, 0, 0, 0))
        ra = self.parser.parse_bytes(a)
        rb = self.parser.parse_bytes(b)
        self.assertNotEqual(ra["package"]["sha256"], rb["package"]["sha256"])
        self.assertEqual([x["physical_hash"] for x in ra["stories"][0]["blocks"]], [x["physical_hash"] for x in rb["stories"][0]["blocks"]])


if __name__ == "__main__":
    unittest.main()
