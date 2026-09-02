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
SW = "http://purl.oclc.org/ooxml/wordprocessingml/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
XML = "http://www.w3.org/XML/1998/namespace"


def qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def paragraph(text: str, ns: str = W) -> etree._Element:
    p = etree.Element(qn(ns, "p"))
    r = etree.SubElement(p, qn(ns, "r"))
    t = etree.SubElement(r, qn(ns, "t"))
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


def make_document(children: list[etree._Element], ns: str = W, body_attrs: dict[str, str] | None = None, encoding: str = "UTF-8") -> bytes:
    root = etree.Element(qn(ns, "document"), nsmap={"w": ns, "r": R})
    body = etree.SubElement(root, qn(ns, "body"), body_attrs or {})
    for child in children:
        body.append(child)
    return etree.tostring(root, xml_declaration=True, encoding=encoding, standalone="yes")


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


def build_docx(document_xml: bytes, entries: list[tuple[str, bytes]] | None = None, timestamp=(2026, 1, 1, 0, 0, 0)) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        parts = [("[Content_Types].xml", content_types()), ("_rels/.rels", package_rels()), ("word/document.xml", document_xml)]
        if entries:
            parts.extend(entries)
        for name, data in parts:
            info = zipfile.ZipInfo(name, timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return buf.getvalue()


class ParserV01Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = DocxParser()

    def test_basic_document(self):
        result = self.parser.parse_bytes(build_docx(make_document([paragraph("A"), paragraph("B"), table(), sectpr()])))
        self.assertEqual(result["status"], "ok")
        blocks = result["stories"][0]["blocks"]
        self.assertEqual([b["source_type"] for b in blocks], ["paragraph", "paragraph", "table", "section_properties"])
        self.assertEqual(blocks[0]["structural_path"], "/w:document/w:body[1]/w:p[1]")
        self.assertTrue(all("canonical_xml" in b for b in blocks))

    def test_determinism_same_input(self):
        data = build_docx(make_document([paragraph("A"), sectpr()]))
        self.assertEqual(serialize_parse_result(self.parser.parse_bytes(data)), serialize_parse_result(self.parser.parse_bytes(data)))

    def test_non_element_nodes_are_preserved_and_protected(self):
        comment = etree.Comment("hello")
        pi = etree.ProcessingInstruction("x", "y")
        result = self.parser.parse_bytes(build_docx(make_document([paragraph("A"), comment, pi, sectpr()])))
        blocks = result["stories"][0]["blocks"]
        self.assertEqual([b["source_type"] for b in blocks], ["paragraph", "non_element_node", "non_element_node", "section_properties"])
        self.assertTrue(blocks[1]["protected"] and blocks[2]["protected"])
        self.assertEqual(sum(1 for w in result["parse_warnings"] if w["code"] == "non_element_child"), 2)

    def test_duplicate_part_is_rejected(self):
        data = build_docx(make_document([paragraph("A"), sectpr()]), entries=[("word/extra.xml", b"<a/>"), ("word/extra.xml", b"<b/>")])
        result = self.parser.parse_bytes(data)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["errors"][0]["code"], "duplicate_part_name")

    def test_inherited_xml_space_changes_physical_hash(self):
        with_space = build_docx(make_document([paragraph("A"), sectpr()], body_attrs={qn(XML, "space"): "preserve"}))
        without_space = build_docx(make_document([paragraph("A"), sectpr()]))
        a = self.parser.parse_bytes(with_space)["stories"][0]["blocks"][0]
        b = self.parser.parse_bytes(without_space)["stories"][0]["blocks"][0]
        self.assertEqual(a["inherited_xml_attrs"]["xml:space"], "preserve")
        self.assertNotEqual(a["physical_hash"], b["physical_hash"])

    def test_strict_namespace_fails_honestly(self):
        result = self.parser.parse_bytes(build_docx(make_document([paragraph("A", SW)], ns=SW)))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["errors"][0]["code"], "unsupported_namespace")

    def test_empty_body_is_valid(self):
        result = self.parser.parse_bytes(build_docx(make_document([])))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stories"][0]["blocks"], [])

    def test_non_utf8_document_xml(self):
        result = self.parser.parse_bytes(build_docx(make_document([paragraph("á"), sectpr()], encoding="ISO-8859-1")))
        self.assertEqual(result["status"], "ok")

    def test_physical_hash_ignores_zip_timestamp(self):
        document = make_document([paragraph("Same"), sectpr()])
        a = build_docx(document, timestamp=(2025, 1, 1, 0, 0, 0))
        b = build_docx(document, timestamp=(2026, 1, 1, 0, 0, 0))
        ra, rb = self.parser.parse_bytes(a), self.parser.parse_bytes(b)
        self.assertNotEqual(ra["package"]["sha256"], rb["package"]["sha256"])
        self.assertEqual([x["physical_hash"] for x in ra["stories"][0]["blocks"]], [x["physical_hash"] for x in rb["stories"][0]["blocks"]])

    def test_errors_are_separate_from_warnings(self):
        result = self.parser.parse_bytes(b"not a zip")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["errors"][0]["code"], "not_a_docx")
        self.assertEqual(result["parse_warnings"], [])

    def test_environment_is_recorded(self):
        result = self.parser.parse_bytes(build_docx(make_document([sectpr()])))
        self.assertIn("lxml", result["environment"])
        self.assertIn("libxml2", result["environment"])


if __name__ == "__main__":
    unittest.main()
