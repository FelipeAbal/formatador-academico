from __future__ import annotations

import hashlib
import unittest

from lxml import etree

from formatador_academico import parser_api
from formatador_academico.patcher.document import parse_document_xml, serialize_document_xml
from formatador_academico.patcher.model import (
    PATCHER_VERSION,
    DOCUMENT_PART,
    PatchResult,
    PatchStatus,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
X = "http://example.com/ns"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


class ParserApiAdversarialTests(unittest.TestCase):
    def test_structural_path_roundtrip_with_slash_bearing_namespace_uri(self):
        root = etree.fromstring(
            f'<w:document xmlns:w="{W}" xmlns:x="{X}">'
            '<w:body><x:weird/><x:weird/></w:body>'
            '</w:document>'.encode("utf-8")
        )
        body = root[0]
        target = body[1]
        path = parser_api.structural_path(target, root)
        self.assertIn("{http://example.com/ns}weird[2]", path)
        self.assertIs(parser_api.resolve_structural_path(root, path), target)


class DocumentSerializationAdversarialTests(unittest.TestCase):
    def test_utf16_declaration_encoding_and_standalone_are_preserved_semantically(self):
        text = (
            '<?xml version="1.0" encoding="UTF-16" standalone="yes"?>'
            '<?before keep?>'
            f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>á</w:t>'
            '</w:r></w:p></w:body></w:document>'
            '<!--after-->'
        )
        original = text.encode("utf-16")
        tree = parse_document_xml(original, "word/document.xml")
        output = serialize_document_xml(tree, original)
        reparsed = parse_document_xml(output, "word/document.xml")

        self.assertEqual(reparsed.docinfo.encoding.upper(), "UTF-16")
        self.assertTrue(reparsed.docinfo.standalone)
        self.assertEqual(reparsed.getroot().xpath("string(.//w:t)", namespaces={"w": W}), "á")
        self.assertIsNotNone(reparsed.getroot().getprevious())
        self.assertIsNotNone(reparsed.getroot().getnext())

    def test_utf16_without_declaration_does_not_gain_one(self):
        text = f'<w:document xmlns:w="{W}"><w:body/></w:document>'
        original = text.encode("utf-16")
        tree = parse_document_xml(original, "word/document.xml")
        output = serialize_document_xml(tree, original)
        decoded = output.decode("utf-16")
        self.assertFalse(decoded.lstrip().startswith("<?xml"))
        reparsed = parse_document_xml(output, "word/document.xml")
        self.assertEqual(reparsed.getroot().tag, f"{{{W}}}document")


class PatchResultAdversarialTests(unittest.TestCase):
    def test_applied_result_rejects_output_hash_not_matching_bytes(self):
        output = b"patched package bytes"
        with self.assertRaises(ValueError):
            PatchResult(
                patcher_version=PATCHER_VERSION,
                status=PatchStatus.APPLIED,
                operation_ref=HEX_A,
                operation_plan_ref=HEX_B,
                input_package_sha256=HEX_C,
                output_package_sha256="d" * 64,
                output_package_bytes=output,
                reason=None,
                changed_part=DOCUMENT_PART,
            )

    def test_applied_result_accepts_matching_output_hash(self):
        output = b"patched package bytes"
        result = PatchResult(
            patcher_version=PATCHER_VERSION,
            status=PatchStatus.APPLIED,
            operation_ref=HEX_A,
            operation_plan_ref=HEX_B,
            input_package_sha256=HEX_C,
            output_package_sha256=hashlib.sha256(output).hexdigest(),
            output_package_bytes=output,
            reason=None,
            changed_part=DOCUMENT_PART,
        )
        self.assertEqual(result.output_package_bytes, output)


if __name__ == "__main__":
    unittest.main()
