from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from lxml import etree

PARSER_VERSION = "0.1.0"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

DOCUMENT_XML = "word/document.xml"
CONTENT_TYPES_XML = "[Content_Types].xml"


@dataclass(frozen=True)
class ParserLimits:
    max_total_uncompressed_bytes: int = 512 * 1024 * 1024
    max_part_uncompressed_bytes: int = 128 * 1024 * 1024
    max_compression_ratio: float = 200.0
    max_parts: int = 10_000


class ParseFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _xml_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        remove_blank_text=False,
        strip_cdata=False,
        recover=False,
        huge_tree=False,
    )


def _reject_doctype(data: bytes, part_name: str) -> None:
    if b"<!DOCTYPE" in data.upper():
        raise ParseFailure(
            "doctype_not_allowed",
            f"DTD/DOCTYPE is not allowed in OOXML part: {part_name}",
        )


def _parse_xml(data: bytes, part_name: str) -> etree._Element:
    _reject_doctype(data, part_name)
    try:
        return etree.fromstring(data, parser=_xml_parser())
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ParseFailure("malformed_xml", f"Malformed XML in {part_name}: {exc}") from exc


def _canonical_xml(node: etree._Element) -> bytes:
    # Inclusive C14N 1.0 is fixed for parser v0.1 and must also be used by the future patcher.
    return etree.tostring(node, method="c14n", exclusive=False, with_comments=True)


def _qname_parts(tag: str) -> tuple[str | None, str]:
    qn = etree.QName(tag)
    return qn.namespace, qn.localname


def _prefixed_name(tag: str) -> str:
    namespace, local = _qname_parts(tag)
    if namespace == W_NS:
        return f"w:{local}"
    return f"{{{namespace}}}{local}" if namespace else local


def _structural_path(node: etree._Element, root: etree._Element) -> str:
    """Return a 1-based, same-tag-sibling positional XPath-like path."""
    elements: list[etree._Element] = []
    current: etree._Element | None = node
    while current is not None:
        elements.append(current)
        if current is root:
            break
        current = current.getparent()
    if not elements or elements[-1] is not root:
        raise ValueError("node is not a descendant of root")

    parts: list[str] = []
    for element in reversed(elements):
        name = _prefixed_name(element.tag)
        parent = element.getparent()
        if parent is None:
            parts.append(name)
            continue
        same_tag = [child for child in parent if child.tag == element.tag]
        index = same_tag.index(element) + 1
        parts.append(f"{name}[{index}]")
    return "/" + "/".join(parts)


def _content_type_maps(content_types_root: etree._Element) -> tuple[dict[str, str], dict[str, str]]:
    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    for child in content_types_root:
        namespace, local = _qname_parts(child.tag)
        if namespace != CT_NS:
            continue
        if local == "Default":
            extension = child.get("Extension")
            content_type = child.get("ContentType")
            if extension and content_type:
                defaults[extension.lower()] = content_type
        elif local == "Override":
            part_name = child.get("PartName")
            content_type = child.get("ContentType")
            if part_name and content_type:
                overrides[part_name.lstrip("/")] = content_type
    return defaults, overrides


def _content_type_for(name: str, defaults: dict[str, str], overrides: dict[str, str]) -> str | None:
    if name in overrides:
        return overrides[name]
    suffix = PurePosixPath(name).suffix.lstrip(".").lower()
    return defaults.get(suffix) if suffix else None


def _relationship_source_part(rels_name: str) -> str:
    if rels_name == "_rels/.rels":
        return "package"
    path = PurePosixPath(rels_name)
    if path.parent.name != "_rels" or not path.name.endswith(".rels"):
        return rels_name
    source_name = path.name[: -len(".rels")]
    source_parent = path.parent.parent
    return str(source_parent / source_name)


def _safe_zip_inventory(zf: zipfile.ZipFile, limits: ParserLimits) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > limits.max_parts:
        raise ParseFailure("zip_too_many_parts", f"ZIP contains {len(infos)} parts; limit is {limits.max_parts}.")

    total = 0
    for info in infos:
        if info.is_dir():
            continue
        if info.file_size > limits.max_part_uncompressed_bytes:
            raise ParseFailure(
                "zip_part_too_large",
                f"Part {info.filename} is {info.file_size} bytes; limit is {limits.max_part_uncompressed_bytes}.",
            )
        total += info.file_size
        if total > limits.max_total_uncompressed_bytes:
            raise ParseFailure(
                "zip_too_large",
                f"ZIP expands to more than {limits.max_total_uncompressed_bytes} bytes.",
            )
        compressed = max(info.compress_size, 1)
        ratio = info.file_size / compressed
        if info.file_size > 1024 * 1024 and ratio > limits.max_compression_ratio:
            raise ParseFailure(
                "zip_suspicious_ratio",
                f"Part {info.filename} has suspicious compression ratio {ratio:.1f}.",
            )
    return infos


def _failed_result(package_sha256: str | None, code: str, message: str) -> dict[str, Any]:
    return {
        "parser_version": PARSER_VERSION,
        "status": "failed",
        "package": {"sha256": package_sha256, "parts": []},
        "relationships": [],
        "stories": [],
        "parse_warnings": [{"code": code, "message": message}],
    }


class DocxParser:
    def __init__(self, limits: ParserLimits | None = None):
        self.limits = limits or ParserLimits()

    def parse_bytes(self, docx_bytes: bytes) -> dict[str, Any]:
        package_sha256 = _sha256(docx_bytes)
        try:
            with zipfile.ZipFile(io.BytesIO(docx_bytes), mode="r") as zf:
                infos = _safe_zip_inventory(zf, self.limits)
                names = {info.filename for info in infos if not info.is_dir()}
                if DOCUMENT_XML not in names:
                    raise ParseFailure("missing_document_xml", f"Missing required part: {DOCUMENT_XML}")
                if CONTENT_TYPES_XML not in names:
                    raise ParseFailure("missing_content_types", f"Missing required part: {CONTENT_TYPES_XML}")

                content_types_data = zf.read(CONTENT_TYPES_XML)
                content_types_root = _parse_xml(content_types_data, CONTENT_TYPES_XML)
                defaults, overrides = _content_type_maps(content_types_root)

                parts: list[dict[str, Any]] = []
                for info in sorted((i for i in infos if not i.is_dir()), key=lambda i: i.filename):
                    data = zf.read(info.filename)
                    parts.append(
                        {
                            "name": info.filename,
                            "size": info.file_size,
                            "sha256": _sha256(data),
                            "content_type": _content_type_for(info.filename, defaults, overrides),
                        }
                    )

                relationships = self._read_relationships(zf, names)
                document_data = zf.read(DOCUMENT_XML)
                document_root = _parse_xml(document_data, DOCUMENT_XML)
                body = document_root.find(f"{{{W_NS}}}body")
                if body is None:
                    raise ParseFailure("missing_body", "word/document.xml has no w:body element")

                blocks: list[dict[str, Any]] = []
                warnings: list[dict[str, Any]] = []

                for original_index, child in enumerate(body):
                    namespace, local = _qname_parts(child.tag)
                    path = _structural_path(child, document_root)
                    raw_c14n = _canonical_xml(child)
                    raw_xml = raw_c14n.decode("utf-8")
                    physical_hash = _sha256(raw_c14n)

                    if namespace == W_NS and local == "p":
                        source_type = "paragraph"
                        protected = False
                    elif namespace == W_NS and local == "tbl":
                        source_type = "table"
                        protected = False
                        warnings.append(
                            {
                                "code": "unparsed_children",
                                "message": "Table interior is preserved as raw XML but not decomposed in parser v0.1.",
                                "structural_path": path,
                            }
                        )
                    elif namespace == W_NS and local == "sectPr":
                        source_type = "section_properties"
                        protected = True
                    else:
                        source_type = "opaque_object"
                        protected = True
                        warnings.append(
                            {
                                "code": "unsupported_body_child",
                                "message": f"Unsupported direct w:body child preserved as opaque object: {_prefixed_name(child.tag)}",
                                "structural_path": path,
                            }
                        )

                    blocks.append(
                        {
                            "id": f"body/block-{original_index + 1:06d}",
                            "source_type": source_type,
                            "structural_path": path,
                            "original_index": original_index,
                            "physical_hash": physical_hash,
                            "raw_xml": raw_xml,
                            "protected": protected,
                        }
                    )

                return {
                    "parser_version": PARSER_VERSION,
                    "status": "ok",
                    "package": {"sha256": package_sha256, "parts": parts},
                    "relationships": relationships,
                    "stories": [
                        {
                            "story_id": "body",
                            "story_type": "body",
                            "part": DOCUMENT_XML,
                            "blocks": blocks,
                        }
                    ],
                    "parse_warnings": warnings,
                }
        except zipfile.BadZipFile:
            return _failed_result(package_sha256, "not_a_docx", "Input is not a valid ZIP/DOCX package.")
        except ParseFailure as exc:
            return _failed_result(package_sha256, exc.code, exc.message)
        except (RuntimeError, OSError, ValueError) as exc:
            return _failed_result(package_sha256, "package_read_error", f"Unable to read DOCX package: {exc}")

    def _read_relationships(self, zf: zipfile.ZipFile, names: set[str]) -> list[dict[str, str]]:
        relationships: list[dict[str, str]] = []
        for name in sorted(n for n in names if n.endswith(".rels")):
            data = zf.read(name)
            root = _parse_xml(data, name)
            source_part = _relationship_source_part(name)
            for child in root:
                namespace, local = _qname_parts(child.tag)
                if namespace != REL_NS or local != "Relationship":
                    continue
                rel_id = child.get("Id")
                rel_type = child.get("Type")
                target = child.get("Target")
                if not (rel_id and rel_type and target):
                    continue
                record = {
                    "part": source_part,
                    "id": rel_id,
                    "type": rel_type,
                    "target": target,
                }
                target_mode = child.get("TargetMode")
                if target_mode:
                    record["target_mode"] = target_mode
                relationships.append(record)
        relationships.sort(key=lambda r: (r["part"], r["id"], r["type"], r["target"]))
        return relationships


def serialize_parse_result(result: dict[str, Any]) -> bytes:
    """Deterministic UTF-8 JSON serialization for parser v0.1."""
    return json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
