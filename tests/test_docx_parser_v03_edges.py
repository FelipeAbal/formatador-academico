from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from formatador_academico.docx_parser import DocxParser  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
RELBASE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
MAINCT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


def qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def document_xml() -> bytes:
    root = etree.Element(qn(W, "document"), nsmap={"w": W})
    body = etree.SubElement(root, qn(W, "body"))
    etree.SubElement(body, qn(W, "p"))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def content_types_xml() -> bytes:
    root = etree.Element(qn(CT, "Types"), nsmap={None: CT})
    etree.SubElement(root, qn(CT, "Default"), Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    etree.SubElement(root, qn(CT, "Default"), Extension="xml", ContentType="application/xml")
    etree.SubElement(root, qn(CT, "Override"), PartName="/word/document.xml", ContentType=MAINCT)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def document_rels_xml() -> bytes:
    root = etree.Element(qn(PR, "Relationships"), nsmap={None: PR})
    etree.SubElement(
        root,
        qn(PR, "Relationship"),
        Id="rBad",
        Type=RELBASE + "footnotes",
        Target="../../../evil.xml",
    )
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def build_docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        timestamp = (2026, 1, 1, 0, 0, 0)
        entries = {
            "[Content_Types].xml": content_types_xml(),
            "word/document.xml": document_xml(),
            "word/_rels/document.xml.rels": document_rels_xml(),
        }
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return buf.getvalue()


class ParserV03EdgeTests(unittest.TestCase):
    def test_suspicious_target_is_rejected_not_missing(self):
        result = DocxParser().parse_bytes(build_docx())
        self.assertEqual(result["status"], "partial")
        story = next(s for s in result["stories"] if s["story_type"] == "footnotes")
        self.assertEqual(story["status"], "rejected")
        self.assertEqual(story["errors"][0]["code"], "suspicious_target")
        self.assertIn(story["story_id"], result["partial_stories"])
        self.assertIn("suspicious_target", [e["code"] for e in result["errors"]])
        self.assertIn("suspicious_target", [w["code"] for w in result["parse_warnings"]])
        self.assertEqual(next(s for s in result["stories"] if s["story_type"] == "body")["status"], "ok")


if __name__ == "__main__":
    unittest.main()
