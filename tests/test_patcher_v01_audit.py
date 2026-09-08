from __future__ import annotations

import unittest

from lxml import etree

from formatador_academico import parser_api
from formatador_academico.patcher.document import parse_document_xml, serialize_document_xml

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
X = "http://example.com/ns"


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


if __name__ == "__main__":
    unittest.main()
