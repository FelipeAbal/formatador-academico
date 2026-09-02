from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import lxml
from lxml import etree

PARSER_VERSION = "0.2.0"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STRICT_W_NS = "http://purl.oclc.org/ooxml/wordprocessingml/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"

DOCUMENT_XML = "word/document.xml"
CONTENT_TYPES_XML = "[Content_Types].xml"
INHERITED_XML_ATTRS = ("space", "lang", "base")

RUN_CONTAINER_TYPES = {"hyperlink", "ins", "del", "fldSimple", "sdt", "sdtContent", "smartTag"}
TEXT_FRAGMENT_TYPES = {
    "t": "text",
    "tab": "tab",
    "br": "break",
    "cr": "carriage_return",
    "noBreakHyphen": "no_break_hyphen",
    "softHyphen": "soft_hyphen",
    "sym": "symbol",
    "instrText": "instruction_text",
    "delText": "deleted_text",
}


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
    return etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False, strip_cdata=False, recover=False, huge_tree=False)


def _reject_doctype(data: bytes, part_name: str) -> None:
    if b"<!DOCTYPE" in data.upper():
        raise ParseFailure("doctype_not_allowed", f"DTD/DOCTYPE is not allowed in OOXML part: {part_name}")


def _parse_xml(data: bytes, part_name: str) -> etree._Element:
    _reject_doctype(data, part_name)
    try:
        return etree.fromstring(data, parser=_xml_parser())
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ParseFailure("malformed_xml", f"Malformed XML in {part_name}: {exc}") from exc


def _canonical_xml(node: etree._Element) -> bytes:
    if not isinstance(node.tag, str):
        return etree.tostring(node, encoding="utf-8", with_tail=False)
    return etree.tostring(node, method="c14n", exclusive=False, with_comments=True)


def _qname_parts(tag: str) -> tuple[str | None, str]:
    qn = etree.QName(tag)
    return qn.namespace, qn.localname


def _prefixed_name(tag: str) -> str:
    namespace, local = _qname_parts(tag)
    if namespace == W_NS:
        return f"w:{local}"
    return f"{{{namespace}}}{local}" if namespace else local


def _node_kind_name(node: etree._Element) -> str:
    if isinstance(node.tag, str):
        return _prefixed_name(node.tag)
    if isinstance(node, etree._Comment):
        return "comment()"
    return "processing-instruction()"


def _structural_path(node: etree._Element, root: etree._Element) -> str:
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
        name = _node_kind_name(element)
        parent = element.getparent()
        if parent is None:
            parts.append(name)
            continue
        same_kind = []
        for child in parent:
            if isinstance(element.tag, str):
                if isinstance(child.tag, str) and child.tag == element.tag:
                    same_kind.append(child)
            elif isinstance(element, etree._Comment):
                if isinstance(child, etree._Comment):
                    same_kind.append(child)
            elif isinstance(child, etree._ProcessingInstruction):
                same_kind.append(child)
        parts.append(f"{name}[{same_kind.index(element) + 1}]")
    return "/" + "/".join(parts)


def _same_kind_index(node: etree._Element) -> int:
    parent = node.getparent()
    if parent is None:
        return 0
    peers = []
    for child in parent:
        if isinstance(node.tag, str):
            if isinstance(child.tag, str) and child.tag == node.tag:
                peers.append(child)
        elif isinstance(node, etree._Comment):
            if isinstance(child, etree._Comment):
                peers.append(child)
        elif isinstance(child, etree._ProcessingInstruction):
            peers.append(child)
    return peers.index(node)


def _inherited_xml_attrs(node: etree._Element) -> dict[str, str]:
    values: dict[str, str] = {}
    chain: list[etree._Element] = []
    current = node.getparent()
    while current is not None:
        chain.append(current)
        current = current.getparent()
    for ancestor in reversed(chain):
        for local in INHERITED_XML_ATTRS:
            key = f"{{{XML_NS}}}{local}"
            if key in ancestor.attrib:
                values[f"xml:{local}"] = ancestor.attrib[key]
    return values


def _own_xml_attrs(node: etree._Element) -> dict[str, str]:
    attrs: dict[str, str] = {}
    if not isinstance(node.tag, str):
        return attrs
    for local in INHERITED_XML_ATTRS:
        key = f"{{{XML_NS}}}{local}"
        if key in node.attrib:
            attrs[f"xml:{local}"] = node.attrib[key]
    return attrs


def _physical_hash(canonical_xml: str, inherited_xml_attrs: dict[str, str]) -> str:
    payload = {"canonical_xml": canonical_xml, "inherited_xml_attrs": inherited_xml_attrs}
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(data)


def _raw_node_record(node: etree._Element, root: etree._Element) -> dict[str, Any]:
    canonical = _canonical_xml(node).decode("utf-8")
    inherited = _inherited_xml_attrs(node)
    return {"structural_path": _structural_path(node, root), "original_index": _same_kind_index(node), "canonical_xml": canonical, "inherited_xml_attrs": inherited, "physical_hash": _physical_hash(canonical, inherited)}


def _properties_record(node: etree._Element, root: etree._Element) -> dict[str, Any]:
    record = _raw_node_record(node, root)
    record["source_type"] = "properties_raw"
    return record


def _fragment_record(node: etree._Element, root: etree._Element, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    record = _raw_node_record(node, root)
    if not isinstance(node.tag, str):
        record.update({"source_type": "non_element_fragment", "protected": True})
        warnings.append({"code": "non_element_run_child", "message": f"Non-element run child preserved: {_node_kind_name(node)}", "structural_path": record["structural_path"]})
        return record
    namespace, local = _qname_parts(node.tag)
    if namespace == W_NS and local in TEXT_FRAGMENT_TYPES:
        record.update({"source_type": "text_fragment", "fragment_type": TEXT_FRAGMENT_TYPES[local], "text": node.text if node.text is not None else "", "xml_attrs": _own_xml_attrs(node), "protected": False})
        if local == "sym":
            record["symbol"] = {"font": node.get(f"{{{W_NS}}}font"), "char": node.get(f"{{{W_NS}}}char")}
        return record
    record.update({"source_type": "opaque_fragment", "protected": True})
    warnings.append({"code": "opaque_run_fragment", "message": f"Run child preserved as opaque fragment: {_prefixed_name(node.tag)}", "structural_path": record["structural_path"]})
    return record


def _parse_run(node: etree._Element, root: etree._Element, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    record = _raw_node_record(node, root)
    record.update({"source_type": "run_raw", "properties_raw": None, "fragments": [], "children": [], "protected": False})
    for child in node:
        if isinstance(child.tag, str):
            namespace, local = _qname_parts(child.tag)
            if namespace == W_NS and local == "rPr":
                if record["properties_raw"] is None:
                    record["properties_raw"] = _properties_record(child, root)
                else:
                    opaque = _fragment_record(child, root, warnings)
                    opaque["source_type"] = "opaque_fragment"
                    opaque["protected"] = True
                    record["children"].append(opaque)
                continue
        fragment = _fragment_record(child, root, warnings)
        record["fragments"].append(fragment)
        record["children"].append(fragment)
    return record


def _parse_run_container(node: etree._Element, root: etree._Element, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    record = _raw_node_record(node, root)
    _, local = _qname_parts(node.tag)
    record.update({"source_type": "run_container", "container_type": local, "children": [], "runs_raw": [], "protected": True})
    warnings.append({"code": "unparsed_container", "message": f"Run container preserved; nested runs decomposed for ordering: w:{local}", "structural_path": record["structural_path"]})
    for child in node:
        if isinstance(child.tag, str):
            namespace, child_local = _qname_parts(child.tag)
            if namespace == W_NS and child_local == "r":
                run = _parse_run(child, root, warnings)
                record["runs_raw"].append(run)
                record["children"].append(run)
                continue
            if namespace == W_NS and child_local in RUN_CONTAINER_TYPES:
                record["children"].append(_parse_run_container(child, root, warnings))
                continue
        opaque = _raw_node_record(child, root)
        opaque.update({"source_type": "opaque_container_child", "protected": True})
        record["children"].append(opaque)
        warnings.append({"code": "opaque_container_child", "message": f"Container child preserved without decomposition: {_node_kind_name(child)}", "structural_path": opaque["structural_path"]})
    return record


def _parse_paragraph(node: etree._Element, root: etree._Element, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    record = _raw_node_record(node, root)
    record.update({"source_type": "paragraph", "properties_raw": None, "children": [], "runs_raw": [], "protected": False})
    for child in node:
        if isinstance(child.tag, str):
            namespace, local = _qname_parts(child.tag)
            if namespace == W_NS and local == "pPr":
                if record["properties_raw"] is None:
                    record["properties_raw"] = _properties_record(child, root)
                else:
                    opaque = _raw_node_record(child, root)
                    opaque.update({"source_type": "opaque_paragraph_child", "protected": True})
                    record["children"].append(opaque)
                    warnings.append({"code": "duplicate_paragraph_properties", "message": "Additional w:pPr preserved as opaque paragraph child.", "structural_path": opaque["structural_path"]})
                continue
            if namespace == W_NS and local == "r":
                run = _parse_run(child, root, warnings)
                record["runs_raw"].append(run)
                record["children"].append(run)
                continue
            if namespace == W_NS and local in RUN_CONTAINER_TYPES:
                record["children"].append(_parse_run_container(child, root, warnings))
                continue
        opaque = _raw_node_record(child, root)
        opaque.update({"source_type": "non_element_paragraph_child" if not isinstance(child.tag, str) else "opaque_paragraph_child", "protected": True})
        record["children"].append(opaque)
        warnings.append({"code": "opaque_paragraph_child", "message": f"Paragraph child preserved without decomposition: {_node_kind_name(child)}", "structural_path": opaque["structural_path"]})
    return record


def _content_type_maps(content_types_root: etree._Element) -> tuple[dict[str, str], dict[str, str]]:
    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    for child in content_types_root:
        if not isinstance(child.tag, str):
            continue
        namespace, local = _qname_parts(child.tag)
        if namespace != CT_NS:
            continue
        if local == "Default":
            extension, content_type = child.get("Extension"), child.get("ContentType")
            if extension and content_type:
                defaults[extension.lower()] = content_type
        elif local == "Override":
            part_name, content_type = child.get("PartName"), child.get("ContentType")
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
    return str(path.parent.parent / path.name[: -len(".rels")])


def _safe_zip_inventory(zf: zipfile.ZipFile, limits: ParserLimits) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > limits.max_parts:
        raise ParseFailure("zip_too_many_parts", f"ZIP contains {len(infos)} parts; limit is {limits.max_parts}.")
    seen: set[str] = set()
    total = 0
    for info in infos:
        if info.is_dir():
            continue
        if info.filename in seen:
            raise ParseFailure("duplicate_part_name", f"Duplicate ZIP part name: {info.filename}")
        seen.add(info.filename)
        if info.file_size > limits.max_part_uncompressed_bytes:
            raise ParseFailure("zip_part_too_large", f"Part {info.filename} exceeds per-part limit.")
        total += info.file_size
        if total > limits.max_total_uncompressed_bytes:
            raise ParseFailure("zip_too_large", "ZIP exceeds total uncompressed size limit.")
        ratio = info.file_size / max(info.compress_size, 1)
        if info.file_size > 1024 * 1024 and ratio > limits.max_compression_ratio:
            raise ParseFailure("zip_suspicious_ratio", f"Part {info.filename} has suspicious compression ratio {ratio:.1f}.")
    return infos


def _environment() -> dict[str, Any]:
    return {"parser": PARSER_VERSION, "lxml": lxml.__version__, "libxml2": ".".join(str(x) for x in etree.LIBXML_VERSION)}


def _failed_result(package_sha256: str | None, code: str, message: str) -> dict[str, Any]:
    return {"parser_version": PARSER_VERSION, "environment": _environment(), "status": "failed", "package": {"sha256": package_sha256, "parts": []}, "relationships": [], "stories": [], "errors": [{"code": code, "message": message}], "parse_warnings": []}


class DocxParser:
    def __init__(self, limits: ParserLimits | None = None):
        self.limits = limits or ParserLimits()

    def _read(self, zf: zipfile.ZipFile, name: str) -> bytes:
        try:
            return zf.read(name)
        except NotImplementedError as exc:
            raise ParseFailure("unsupported_compression", f"Unsupported compression for part {name}: {exc}") from exc
        except (OSError, RuntimeError, KeyError) as exc:
            raise ParseFailure("package_read_error", f"Unable to read part {name}: {exc}") from exc

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
                content_types_root = _parse_xml(self._read(zf, CONTENT_TYPES_XML), CONTENT_TYPES_XML)
                defaults, overrides = _content_type_maps(content_types_root)
                parts: list[dict[str, Any]] = []
                for info in sorted((i for i in infos if not i.is_dir()), key=lambda i: i.filename):
                    data = self._read(zf, info.filename)
                    parts.append({"name": info.filename, "size": info.file_size, "sha256": _sha256(data), "content_type": _content_type_for(info.filename, defaults, overrides)})
                relationships = self._read_relationships(zf, names)
                document_root = _parse_xml(self._read(zf, DOCUMENT_XML), DOCUMENT_XML)
                if not isinstance(document_root.tag, str):
                    raise ParseFailure("unsupported_namespace", "word/document.xml root is not an element.")
                root_ns, root_local = _qname_parts(document_root.tag)
                if root_local != "document" or root_ns != W_NS:
                    if root_ns == STRICT_W_NS:
                        raise ParseFailure("unsupported_namespace", f"Strict OOXML namespace is not supported in v0.2: {root_ns}")
                    raise ParseFailure("unsupported_namespace", f"Unsupported WordprocessingML namespace/root: {root_ns} {root_local}")
                body = document_root.find(f"{{{W_NS}}}body")
                if body is None:
                    raise ParseFailure("missing_body", "word/document.xml has no w:body element")
                blocks: list[dict[str, Any]] = []
                warnings: list[dict[str, Any]] = []
                for original_index, child in enumerate(body):
                    if isinstance(child.tag, str):
                        namespace, local = _qname_parts(child.tag)
                        if namespace == W_NS and local == "p":
                            block = _parse_paragraph(child, document_root, warnings)
                            block.update({"id": f"body/block-{original_index + 1:06d}", "original_index": original_index})
                            blocks.append(block)
                            continue
                    path = _structural_path(child, document_root)
                    canonical = _canonical_xml(child).decode("utf-8")
                    inherited = _inherited_xml_attrs(child)
                    p_hash = _physical_hash(canonical, inherited)
                    if not isinstance(child.tag, str):
                        source_type, protected = "non_element_node", True
                        node_kind = "comment" if isinstance(child, etree._Comment) else "processing_instruction"
                        warnings.append({"code": "non_element_child", "message": f"Non-element body child preserved and protected: {node_kind}", "structural_path": path})
                    else:
                        namespace, local = _qname_parts(child.tag)
                        if namespace == W_NS and local == "tbl":
                            source_type, protected = "table", False
                            warnings.append({"code": "unparsed_children", "message": "Table interior is preserved as canonical XML but not decomposed in parser v0.2.", "structural_path": path})
                        elif namespace == W_NS and local == "sectPr":
                            source_type, protected = "section_properties", True
                        else:
                            source_type, protected = "opaque_object", True
                            warnings.append({"code": "unsupported_body_child", "message": f"Unsupported direct w:body child preserved as opaque object: {_prefixed_name(child.tag)}", "structural_path": path})
                    blocks.append({"id": f"body/block-{original_index + 1:06d}", "source_type": source_type, "structural_path": path, "original_index": original_index, "physical_hash": p_hash, "canonical_xml": canonical, "inherited_xml_attrs": inherited, "protected": protected})
                return {"parser_version": PARSER_VERSION, "environment": _environment(), "status": "ok", "package": {"sha256": package_sha256, "parts": parts}, "relationships": relationships, "stories": [{"story_id": "body", "story_type": "body", "part": DOCUMENT_XML, "blocks": blocks}], "errors": [], "parse_warnings": warnings}
        except zipfile.BadZipFile:
            return _failed_result(package_sha256, "not_a_docx", "Input is not a valid ZIP/DOCX package.")
        except ParseFailure as exc:
            return _failed_result(package_sha256, exc.code, exc.message)

    def _read_relationships(self, zf: zipfile.ZipFile, names: set[str]) -> list[dict[str, str]]:
        relationships: list[dict[str, str]] = []
        for name in sorted(n for n in names if n.endswith(".rels")):
            root = _parse_xml(self._read(zf, name), name)
            source_part = _relationship_source_part(name)
            for child in root:
                if not isinstance(child.tag, str):
                    continue
                namespace, local = _qname_parts(child.tag)
                if namespace != REL_NS or local != "Relationship":
                    continue
                rel_id, rel_type, target = child.get("Id"), child.get("Type"), child.get("Target")
                if not (rel_id and rel_type and target):
                    continue
                record = {"part": source_part, "id": rel_id, "type": rel_type, "target": target}
                if child.get("TargetMode"):
                    record["target_mode"] = child.get("TargetMode")
                relationships.append(record)
        relationships.sort(key=lambda r: (r["part"], r["id"], r["type"], r["target"]))
        return relationships


def serialize_parse_result(result: dict[str, Any]) -> bytes:
    return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
