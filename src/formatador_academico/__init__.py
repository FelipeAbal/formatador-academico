"""Formatador Acadêmico core package."""

from .docx_parser import DocxParser, ParserLimits, serialize_parse_result

__all__ = ["DocxParser", "ParserLimits", "serialize_parse_result"]
