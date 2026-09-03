from __future__ import annotations

import hashlib
import io
import json
import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import lxml
from lxml import etree

PARSER_VERSION = "0.3.0"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STRICT_W_NS = "http://purl.oclc.org/ooxml/wordprocessingml/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"

DOCUMENT_XML = "word/document.xml"
CONTENT_TYPES_XML = "[Content_Types].xml"
INHERITED_XML_ATTRS = ("space", "lang", "base")

RUN_CONTAINER_TYPES = {
    "hyperlink", "ins", "del", "fldSimple", "sdt", "sdtContent",
    "smartTag", "bdo", "dir", "customXml",
}
TEXT_FRAGMENT_TYPES = {
    "t": "text", "tab": "tab", "br": "break", "cr": "carriage_return",
    "noBreakHyphen": "no_break_hyphen", "softHyphen": "soft_hyphen",
    "sym": "symbol", "instrText": "instruction_text", "delText": "deleted_text",
}

OFFICE_REL_PREFIX = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
STORY_REL_TYPES = {
    OFFICE_REL_PREFIX + "footnotes": "footnotes",
    OFFICE_REL_PREFIX + "endnotes": "endnotes",
    OFFICE_REL_PREFIX + "header": "header",
    OFFICE_REL_PREFIX + "footer": "footer",
    OFFICE_REL_PREFIX + "comments": "comments",
}
STORY_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml": "footnotes",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml": "endnotes",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml": "header",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml": "footer",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml": "comments",
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
        self.code, self.message = code, message

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _xml_parser() -> etree.XMLParser:
    return etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False,
                           strip_cdata=False, recover=False, huge_tree=False)

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
    ns, local = _qname_parts(tag)
    if ns == W_NS:
        return f"w:{local}"
    return f"{{{ns}}}{local}" if ns else local

def _node_kind_name(node: etree._Element) -> str:
    if isinstance(node.tag, str): return _prefixed_name(node.tag)
    if isinstance(node, etree._Comment): return "comment()"
    return "processing-instruction()"

def _structural_path(node: etree._Element, root: etree._Element) -> str:
    chain=[]; cur=node
    while cur is not None:
        chain.append(cur)
        if cur is root: break
        cur=cur.getparent()
    if not chain or chain[-1] is not root:
        raise ValueError("node is not a descendant of root")
    parts=[]
    for el in reversed(chain):
        name=_node_kind_name(el)
        parent=el.getparent()
        if parent is None:
            parts.append(name); continue
        if isinstance(el.tag,str):
            peers=[c for c in parent if isinstance(c.tag,str) and c.tag==el.tag]
        elif isinstance(el, etree._Comment):
            peers=[c for c in parent if isinstance(c, etree._Comment)]
        else:
            peers=[c for c in parent if isinstance(c, etree._ProcessingInstruction)]
        parts.append(f"{name}[{peers.index(el)+1}]")
    return "/" + "/".join(parts)

def _child_index(node: etree._Element) -> int:
    parent=node.getparent()
    return 0 if parent is None else list(parent).index(node)

def _inherited_xml_attrs(node: etree._Element) -> dict[str,str]:
    values={}; chain=[]; cur=node.getparent()
    while cur is not None:
        chain.append(cur); cur=cur.getparent()
    for anc in reversed(chain):
        for local in INHERITED_XML_ATTRS:
            k=f"{{{XML_NS}}}{local}"
            if k in anc.attrib: values[f"xml:{local}"]=anc.attrib[k]
    return values

def _own_xml_attrs(node: etree._Element) -> dict[str,str]:
    attrs={}
    if not isinstance(node.tag,str): return attrs
    for local in INHERITED_XML_ATTRS:
        k=f"{{{XML_NS}}}{local}"
        if k in node.attrib: attrs[f"xml:{local}"]=node.attrib[k]
    return attrs

def _physical_hash(canonical_xml: str, inherited_xml_attrs: dict[str,str]) -> str:
    payload={"canonical_xml":canonical_xml,"inherited_xml_attrs":inherited_xml_attrs}
    return _sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())

def _raw_node_record(node, root):
    canonical=_canonical_xml(node).decode("utf-8")
    inherited=_inherited_xml_attrs(node)
    return {"structural_path":_structural_path(node,root),"original_index":_child_index(node),
            "canonical_xml":canonical,"inherited_xml_attrs":inherited,
            "physical_hash":_physical_hash(canonical,inherited)}

def _warn(warnings, code, message, path=None, story_id=None):
    w={"code":code,"message":message}
    if path: w["structural_path"]=path
    if story_id: w["story_id"]=story_id
    warnings.append(w)

def _warn_mixed_content(node, root, warnings, story_id=None, allow_text=False):
    if not allow_text and node.text and node.text.strip():
        _warn(warnings,"mixed_content_text","Unexpected direct text preserved only in canonical XML.",
              _structural_path(node,root),story_id)
    for child in node:
        if child.tail and child.tail.strip():
            _warn(warnings,"mixed_content_text","Unexpected tail text preserved only in canonical XML.",
                  _structural_path(child,root),story_id)

def _aggregate_warnings(warnings):
    grouped={}
    for w in warnings:
        key=(w.get("story_id"),w["code"],w["message"])
        item=grouped.setdefault(key,{"code":w["code"],"message":w["message"],"count":0,"sample_paths":[]})
        if w.get("story_id") is not None: item["story_id"]=w["story_id"]
        item["count"]+=1
        if w.get("structural_path") and len(item["sample_paths"])<3:
            item["sample_paths"].append(w["structural_path"])
    return sorted(grouped.values(),key=lambda x:(x.get("story_id",""),x["code"],x["message"]))

def _detect_textbox(node, root, warnings, story_id=None):
    if not isinstance(node.tag,str):
        return
    textbox_tags = (
        f"{{{W_NS}}}txbxContent",
        f"{{{A_NS}}}txBody",
        f"{{{P_NS}}}txBody",
    )
    detected = node.tag in textbox_tags or any(node.find(f".//{tag}") is not None for tag in textbox_tags)
    if detected:
        _warn(warnings,"textbox_detected","Textbox/text-body content detected inside opaque XML and not decomposed.",
              _structural_path(node,root),story_id)

def _properties_record(node, root):
    r=_raw_node_record(node,root); r["source_type"]="properties_raw"; return r

def _fragment_record(node, root, warnings, story_id=None):
    record=_raw_node_record(node,root)
    if not isinstance(node.tag,str):
        record.update({"source_type":"non_element_fragment","protected":True})
        _warn(warnings,"non_element_run_child",f"Non-element run child preserved: {_node_kind_name(node)}",
              record["structural_path"],story_id)
        return record
    ns,local=_qname_parts(node.tag)
    if ns==W_NS and local in TEXT_FRAGMENT_TYPES:
        record.update({"source_type":"text_fragment","fragment_type":TEXT_FRAGMENT_TYPES[local],
                       "text":node.text or "","xml_attrs":_own_xml_attrs(node),"protected":False})
        if local=="sym":
            record["symbol"]={"font":node.get(f"{{{W_NS}}}font"),"char":node.get(f"{{{W_NS}}}char")}
        return record
    record.update({"source_type":"opaque_fragment","protected":True})
    _detect_textbox(node,root,warnings,story_id)
    _warn(warnings,"opaque_run_fragment",f"Run child preserved as opaque fragment: {_prefixed_name(node.tag)}",
          record["structural_path"],story_id)
    return record

def _parse_run(node, root, warnings, story_id=None):
    _warn_mixed_content(node,root,warnings,story_id)
    r=_raw_node_record(node,root)
    r.update({"source_type":"run_raw","properties_raw":None,"fragment_refs":[],"children":[],"protected":False})
    for child in node:
        if isinstance(child.tag,str):
            ns,local=_qname_parts(child.tag)
            if ns==W_NS and local=="rPr":
                if r["properties_raw"] is None:
                    r["properties_raw"]=_properties_record(child,root)
                else:
                    opaque=_raw_node_record(child,root); opaque.update({"source_type":"opaque_fragment","protected":True})
                    r["children"].append(opaque)
                    _warn(warnings,"duplicate_run_properties","Additional w:rPr preserved as opaque run child.",
                          opaque["structural_path"],story_id)
                continue
        f=_fragment_record(child,root,warnings,story_id)
        r["fragment_refs"].append(f["structural_path"]); r["children"].append(f)
    return r

def _parse_run_container(node, root, warnings, story_id=None):
    _warn_mixed_content(node,root,warnings,story_id)
    r=_raw_node_record(node,root); _,local=_qname_parts(node.tag)
    r.update({"source_type":"run_container","container_type":local,"children":[],"run_refs":[],"protected":True})
    _warn(warnings,"unparsed_container",f"Run container preserved; nested runs decomposed for ordering: w:{local}",
          r["structural_path"],story_id)
    for child in node:
        if isinstance(child.tag,str):
            ns,cl=_qname_parts(child.tag)
            if ns==W_NS and cl=="r":
                run=_parse_run(child,root,warnings,story_id)
                r["run_refs"].append(run["structural_path"]); r["children"].append(run); continue
            if ns==W_NS and cl in RUN_CONTAINER_TYPES:
                r["children"].append(_parse_run_container(child,root,warnings,story_id)); continue
        opaque=_raw_node_record(child,root); opaque.update({"source_type":"opaque_container_child","protected":True})
        _detect_textbox(child,root,warnings,story_id)
        r["children"].append(opaque)
        _warn(warnings,"opaque_container_child",f"Container child preserved without decomposition: {_node_kind_name(child)}",
              opaque["structural_path"],story_id)
    return r

def _parse_paragraph(node, root, warnings, story_id=None):
    _warn_mixed_content(node,root,warnings,story_id)
    r=_raw_node_record(node,root)
    r.update({"source_type":"paragraph","properties_raw":None,"children":[],"run_refs":[],"protected":False})
    for child in node:
        if isinstance(child.tag,str):
            ns,local=_qname_parts(child.tag)
            if ns==W_NS and local=="pPr":
                if r["properties_raw"] is None: r["properties_raw"]=_properties_record(child,root)
                else:
                    opaque=_raw_node_record(child,root); opaque.update({"source_type":"opaque_paragraph_child","protected":True})
                    r["children"].append(opaque)
                    _warn(warnings,"duplicate_paragraph_properties","Additional w:pPr preserved as opaque paragraph child.",
                          opaque["structural_path"],story_id)
                continue
            if ns==W_NS and local=="r":
                run=_parse_run(child,root,warnings,story_id)
                r["run_refs"].append(run["structural_path"]); r["children"].append(run); continue
            if ns==W_NS and local in RUN_CONTAINER_TYPES:
                r["children"].append(_parse_run_container(child,root,warnings,story_id)); continue
        opaque=_raw_node_record(child,root)
        opaque.update({"source_type":"non_element_paragraph_child" if not isinstance(child.tag,str) else "opaque_paragraph_child",
                       "protected":True})
        _detect_textbox(child,root,warnings,story_id)
        r["children"].append(opaque)
        _warn(warnings,"opaque_paragraph_child",f"Paragraph child preserved without decomposition: {_node_kind_name(child)}",
              opaque["structural_path"],story_id)
    return r

def _parse_block_sequence(container, root, warnings, story_id, *, allow_sectpr=False):
    blocks=[]
    for original_index, child in enumerate(container):
        if isinstance(child.tag,str):
            ns,local=_qname_parts(child.tag)
            if ns==W_NS and local=="p":
                block=_parse_paragraph(child,root,warnings,story_id)
                block.update({"id":f"{story_id}/block-{original_index+1:06d}","original_index":original_index})
                blocks.append(block); continue
        rec=_raw_node_record(child,root)
        if not isinstance(child.tag,str):
            source_type,protected="non_element_node",True
            _warn(warnings,"non_element_child",
                  f"Non-element story child preserved and protected: {_node_kind_name(child)}",
                  rec["structural_path"],story_id)
        else:
            ns,local=_qname_parts(child.tag)
            if ns==W_NS and local=="tbl":
                source_type,protected="table",False
                _detect_textbox(child,root,warnings,story_id)
                _warn(warnings,"unparsed_children","Table interior is preserved as canonical XML but not decomposed.",
                      rec["structural_path"],story_id)
            elif allow_sectpr and ns==W_NS and local=="sectPr":
                source_type,protected="section_properties",True
            else:
                source_type,protected="opaque_object",True
                _detect_textbox(child,root,warnings,story_id)
                _warn(warnings,"unsupported_story_child",
                      f"Unsupported direct story child preserved as opaque object: {_node_kind_name(child)}",
                      rec["structural_path"],story_id)
        rec.update({"id":f"{story_id}/block-{original_index+1:06d}","source_type":source_type,
                    "original_index":original_index,"protected":protected})
        blocks.append(rec)
    return blocks

def _content_type_maps(root):
    defaults={}; overrides={}
    for child in root:
        if not isinstance(child.tag,str): continue
        ns,local=_qname_parts(child.tag)
        if ns!=CT_NS: continue
        if local=="Default" and child.get("Extension") and child.get("ContentType"):
            defaults[child.get("Extension").lower()]=child.get("ContentType")
        elif local=="Override" and child.get("PartName") and child.get("ContentType"):
            overrides[child.get("PartName").lstrip("/")]=child.get("ContentType")
    return defaults,overrides

def _content_type_for(name,defaults,overrides):
    if name in overrides: return overrides[name]
    suffix=PurePosixPath(name).suffix.lstrip(".").lower()
    return defaults.get(suffix) if suffix else None

def _relationship_source_part(rels_name):
    if rels_name=="_rels/.rels": return "package"
    path=PurePosixPath(rels_name)
    if path.parent.name!="_rels" or not path.name.endswith(".rels"): return rels_name
    return str(path.parent.parent / path.name[:-5])

def _resolve_target(source_part, target):
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    base="" if source_part=="package" else posixpath.dirname(source_part)
    return posixpath.normpath(posixpath.join(base,target))

def _safe_zip_inventory(zf,limits):
    infos=zf.infolist()
    if len(infos)>limits.max_parts: raise ParseFailure("zip_too_many_parts",f"ZIP contains {len(infos)} parts; limit is {limits.max_parts}.")
    seen=set(); total=0
    for info in infos:
        if info.is_dir(): continue
        if info.filename in seen: raise ParseFailure("duplicate_part_name",f"Duplicate ZIP part name: {info.filename}")
        seen.add(info.filename)
        if info.file_size>limits.max_part_uncompressed_bytes: raise ParseFailure("zip_part_too_large",f"Part {info.filename} exceeds per-part limit.")
        total+=info.file_size
        if total>limits.max_total_uncompressed_bytes: raise ParseFailure("zip_too_large","ZIP exceeds total uncompressed size limit.")
        ratio=info.file_size/max(info.compress_size,1)
        if info.file_size>1024*1024 and ratio>limits.max_compression_ratio:
            raise ParseFailure("zip_suspicious_ratio",f"Part {info.filename} has suspicious compression ratio {ratio:.1f}.")
    return infos

def _environment():
    return {"parser":PARSER_VERSION,"lxml":lxml.__version__,"libxml2":".".join(str(x) for x in etree.LIBXML_VERSION)}

def _failed_result(package_sha256,code,message):
    return {"parser_version":PARSER_VERSION,"environment":_environment(),"status":"failed",
            "partial_stories":[],"package":{"sha256":package_sha256,"parts":[]},"relationships":[],"stories":[],
            "errors":[{"code":code,"message":message}],"parse_warnings":[]}

class DocxParser:
    def __init__(self, limits: ParserLimits|None=None):
        self.limits=limits or ParserLimits()

    def _read(self,zf,name):
        try: return zf.read(name)
        except NotImplementedError as exc:
            raise ParseFailure("unsupported_compression",f"Unsupported compression for part {name}: {exc}") from exc
        except (OSError,RuntimeError,KeyError) as exc:
            raise ParseFailure("package_read_error",f"Unable to read part {name}: {exc}") from exc

    def _read_relationships(self,zf,names):
        rels=[]
        for name in sorted(n for n in names if n.endswith(".rels")):
            root=_parse_xml(self._read(zf,name),name)
            source=_relationship_source_part(name)
            for child in root:
                if not isinstance(child.tag,str): continue
                ns,local=_qname_parts(child.tag)
                if ns!=REL_NS or local!="Relationship": continue
                rid,rtype,target=child.get("Id"),child.get("Type"),child.get("Target")
                if not (rid and rtype and target): continue
                rec={"part":source,"id":rid,"type":rtype,"target":target}
                if child.get("TargetMode"): rec["target_mode"]=child.get("TargetMode")
                if child.get("TargetMode")!="External":
                    rec["resolved_target"]=_resolve_target(source,target)
                rels.append(rec)
        rels.sort(key=lambda r:(r["part"],r["id"],r["type"],r["target"]))
        return rels

    def _story_error(self, story_id, story_type, part, relationship_id, code, message, status="failed"):
        return {"story_id":story_id,"story_type":story_type,"part":part,"relationship_id":relationship_id,
                "status":status,"errors":[{"code":code,"message":message}],
                "blocks":[] if story_type in ("header","footer") else None,
                "items":[] if story_type in ("footnotes","endnotes","comments") else None,
                "opaque_items":[] if story_type in ("footnotes","endnotes","comments") else None}

    def _parse_block_story(self,zf,part,story_type,story_id,relationship_id,warnings):
        try:
            root=_parse_xml(self._read(zf,part),part)
            if not isinstance(root.tag,str): raise ParseFailure("unsupported_story_namespace","Story root is not an element.")
            ns,local=_qname_parts(root.tag)
            expected={"header":"hdr","footer":"ftr"}[story_type]
            if ns!=W_NS or local!=expected:
                raise ParseFailure("unsupported_story_namespace",f"Unexpected {story_type} root: {ns} {local}")
            blocks=_parse_block_sequence(root,root,warnings,story_id)
            return {"story_id":story_id,"story_type":story_type,"part":part,"relationship_id":relationship_id,
                    "status":"ok","blocks":blocks,"items":None,"opaque_items":None,"errors":[]}
        except ParseFailure as exc:
            return self._story_error(story_id,story_type,part,relationship_id,exc.code,exc.message)

    def _parse_item_story(self,zf,part,story_type,story_id,relationship_id,warnings):
        tag_map={"footnotes":("footnotes","footnote","note_id","note_type"),
                 "endnotes":("endnotes","endnote","note_id","note_type"),
                 "comments":("comments","comment","comment_id",None)}
        root_local,item_local,id_field,type_field=tag_map[story_type]
        try:
            root=_parse_xml(self._read(zf,part),part)
            if not isinstance(root.tag,str): raise ParseFailure("unsupported_story_namespace","Story root is not an element.")
            ns,local=_qname_parts(root.tag)
            if ns!=W_NS or local!=root_local:
                raise ParseFailure("unsupported_story_namespace",f"Unexpected {story_type} root: {ns} {local}")
            items=[]
            represented_paths=[]
            seen_item_ids: set[str] = set()
            for child in root:
                if isinstance(child.tag,str):
                    cns,clocal=_qname_parts(child.tag)
                    if cns==W_NS and clocal==item_local:
                        rec=_raw_node_record(child,root)
                        item_id=child.get(f"{{{W_NS}}}id")
                        if item_id is None:
                            code = "missing_comment_id" if story_type == "comments" else "missing_note_id"
                            _warn(warnings,code,f"{story_type} item is missing w:id.",rec["structural_path"],story_id)
                        elif item_id in seen_item_ids:
                            code = "duplicate_comment_id" if story_type == "comments" else "duplicate_note_id"
                            _warn(warnings,code,f"Duplicate w:id in {story_type}: {item_id}",rec["structural_path"],story_id)
                        else:
                            seen_item_ids.add(item_id)
                        item={"structural_path":rec["structural_path"],"original_index":rec["original_index"],
                              "canonical_xml":rec["canonical_xml"],"inherited_xml_attrs":rec["inherited_xml_attrs"],
                              "physical_hash":rec["physical_hash"],id_field:item_id,
                              "blocks":_parse_block_sequence(child,root,warnings,story_id)}
                        if type_field: item[type_field]=child.get(f"{{{W_NS}}}type")
                        items.append(item); represented_paths.append(rec["structural_path"]); continue
                rec=_raw_node_record(child,root)
                represented_paths.append(rec["structural_path"])
                _detect_textbox(child,root,warnings,story_id)
                _warn(warnings,"unsupported_story_child",
                      f"Unsupported direct {story_type} root child preserved only in story canonical coverage: {_node_kind_name(child)}",
                      rec["structural_path"],story_id)
            opaque_items=[]
            item_paths={x["structural_path"] for x in items}
            for child in root:
                p=_structural_path(child,root)
                if p not in item_paths:
                    rec=_raw_node_record(child,root); rec.update({"source_type":"opaque_story_child","protected":True})
                    opaque_items.append(rec)
            return {"story_id":story_id,"story_type":story_type,"part":part,"relationship_id":relationship_id,
                    "status":"ok","blocks":None,"items":items,"opaque_items":opaque_items,"errors":[]}
        except ParseFailure as exc:
            return self._story_error(story_id,story_type,part,relationship_id,exc.code,exc.message)

    def parse_bytes(self,docx_bytes):
        package_sha256=_sha256(docx_bytes)
        try:
            with zipfile.ZipFile(io.BytesIO(docx_bytes),"r") as zf:
                infos=_safe_zip_inventory(zf,self.limits)
                names={i.filename for i in infos if not i.is_dir()}
                if DOCUMENT_XML not in names: raise ParseFailure("missing_document_xml",f"Missing required part: {DOCUMENT_XML}")
                if CONTENT_TYPES_XML not in names: raise ParseFailure("missing_content_types",f"Missing required part: {CONTENT_TYPES_XML}")
                ct_root=_parse_xml(self._read(zf,CONTENT_TYPES_XML),CONTENT_TYPES_XML)
                defaults,overrides=_content_type_maps(ct_root)
                parts=[]
                part_ct={}
                for info in sorted((i for i in infos if not i.is_dir()),key=lambda i:i.filename):
                    data=self._read(zf,info.filename)
                    ctype=_content_type_for(info.filename,defaults,overrides); part_ct[info.filename]=ctype
                    parts.append({"name":info.filename,"size":info.file_size,"sha256":_sha256(data),"content_type":ctype})
                relationships=self._read_relationships(zf,names)

                doc_root=_parse_xml(self._read(zf,DOCUMENT_XML),DOCUMENT_XML)
                if not isinstance(doc_root.tag,str): raise ParseFailure("unsupported_namespace","word/document.xml root is not an element.")
                rns,rlocal=_qname_parts(doc_root.tag)
                if rlocal!="document" or rns!=W_NS:
                    raise ParseFailure("unsupported_namespace",f"Unsupported WordprocessingML namespace/root: {rns} {rlocal}")
                body=doc_root.find(f"{{{W_NS}}}body")
                if body is None: raise ParseFailure("missing_body","word/document.xml has no w:body element")

                warnings=[]; errors=[]
                stories=[{"story_id":"body","story_type":"body","part":DOCUMENT_XML,"relationship_id":None,
                          "status":"ok","blocks":_parse_block_sequence(body,doc_root,warnings,"body",allow_sectpr=True),
                          "items":None,"opaque_items":None,"errors":[]}]

                doc_story_rels=[r for r in relationships if r["part"]==DOCUMENT_XML and r["type"] in STORY_REL_TYPES and r.get("target_mode")!="External"]
                seen_parts=set()
                seen_story_types: dict[str, str] = {}
                for rel in doc_story_rels:
                    stype=STORY_REL_TYPES[rel["type"]]
                    part=rel.get("resolved_target")
                    sid=f"{stype}:{part}"
                    previous_part = seen_story_types.get(stype)
                    if previous_part is not None and previous_part != part:
                        _warn(warnings,"duplicate_story_type",
                              f"Multiple parts are related as story type {stype}: {previous_part}, {part}",story_id=sid)
                    else:
                        seen_story_types[stype] = part
                    if part and (part == ".." or part.startswith("../")):
                        _warn(warnings,"suspicious_target",f"Resolved story target escapes package root: {part}",story_id=sid)
                    if part in seen_parts:
                        _warn(warnings,"duplicate_story_relationship",f"Multiple story relationships target the same part: {part}",story_id=sid)
                        continue
                    seen_parts.add(part)
                    if part not in names:
                        story=self._story_error(sid,stype,part,rel["id"],"missing_related_part",
                                                f"Relationship {rel['id']} points to missing part {part}.",status="missing")
                        stories.append(story)
                        errors.append({"code":"missing_related_part","message":f"{sid}: missing part {part}","story_id":sid})
                        continue
                    expected_ctype=next((ctype for ctype,kind in STORY_CONTENT_TYPES.items() if kind==stype),None)
                    actual_ctype=part_ct.get(part)
                    if expected_ctype and actual_ctype != expected_ctype:
                        _warn(warnings,"story_type_mismatch",
                              f"Relationship type {stype} disagrees with content type {actual_ctype!r}; relationship type used.",
                              story_id=sid)
                    if stype in ("header","footer"):
                        story=self._parse_block_story(zf,part,stype,sid,rel["id"],warnings)
                    else:
                        story=self._parse_item_story(zf,part,stype,sid,rel["id"],warnings)
                    stories.append(story)
                    if story["status"]!="ok":
                        errors.extend({**e,"story_id":sid} for e in story["errors"])

                for part,ctype in sorted(part_ct.items()):
                    stype=STORY_CONTENT_TYPES.get(ctype)
                    if not stype or part in seen_parts: continue
                    sid=f"{stype}:{part}"
                    _warn(warnings,"orphan_story_part",f"Known story part exists without document relationship: {part}",story_id=sid)
                    if stype in ("header","footer"):
                        story=self._parse_block_story(zf,part,stype,sid,None,warnings)
                    else:
                        story=self._parse_item_story(zf,part,stype,sid,None,warnings)
                    stories.append(story)
                    if story["status"]!="ok": errors.extend({**e,"story_id":sid} for e in story["errors"])

                ids=[s["story_id"] for s in stories]; sparts=[s["part"] for s in stories]
                if len(sparts)!=len(set(sparts)):
                    raise ParseFailure("duplicate_story_part","Duplicate physical story part after discovery.")
                if len(ids)!=len(set(ids)):
                    raise ParseFailure("duplicate_story_identity","Unexpected story_id collision after part-based identity derivation.")

                partial_stories=[s["story_id"] for s in stories[1:] if s["status"]!="ok"]
                overall_status="partial" if partial_stories else "ok"
                return {"parser_version":PARSER_VERSION,"environment":_environment(),"status":overall_status,
                        "partial_stories":partial_stories,
                        "package":{"sha256":package_sha256,"parts":parts},"relationships":relationships,
                        "stories":stories,"errors":errors,"parse_warnings":_aggregate_warnings(warnings)}
        except zipfile.BadZipFile:
            return _failed_result(package_sha256,"not_a_docx","Input is not a valid ZIP/DOCX package.")
        except ParseFailure as exc:
            return _failed_result(package_sha256,exc.code,exc.message)

def serialize_parse_result(result):
    return json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
