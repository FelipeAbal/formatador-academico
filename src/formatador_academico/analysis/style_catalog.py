"""StyleCatalog — analytical projection of word/styles.xml (v0.1b Marco 1).

The catalog is derived directly from the immutable OriginalPackage bytes, NOT
from the PhysicalIR tree. Integrity is verified by part name + sha256 against
the PhysicalIR package inventory. styles.xml never becomes part of the
PhysicalIR and the parser v0.4 is not reopened.
"""

from __future__ import annotations

import hashlib
import io
import zipfile

from lxml import etree

from ..docx_parser import W_NS, _canonical_xml, _physical_hash
from .formatting_model import (
    STYLES_PART_NAME,
    W_DUPLICATE_STYLE_ID,
    W_MULTIPLE_DEFAULT_STYLES,
    W_STYLES_PART_UNREADABLE,
    DocDefaults,
    StyleCatalog,
    StyleEntry,
)
from .model import AnalysisWarning
from .property_bag import _bag_from_element

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)

_TRUE_TOKENS = {"1", "true", "on"}


def _q(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _attr(node: etree._Element, local: str) -> str | None:
    return node.get(_q(local))


def _truthy(value: str | None) -> bool:
    return value is not None and value.lower() in _TRUE_TOKENS


def _read_styles_bytes(package_bytes: bytes) -> bytes | None:
    try:
        with zipfile.ZipFile(io.BytesIO(package_bytes), "r") as zf:
            names = set(zf.namelist())
            if STYLES_PART_NAME not in names:
                return None
            return zf.read(STYLES_PART_NAME)
    except zipfile.BadZipFile:
        return None


def _inventory_sha256(physical_ir: dict) -> str | None:
    package = physical_ir.get("package") or {}
    for part in package.get("parts") or []:
        if part.get("name") == STYLES_PART_NAME:
            return part.get("sha256")
    return None


def _style_entry(node: etree._Element, index: int) -> StyleEntry:
    base_path = f"/w:styles/w:style[{index + 1}]"
    canonical = _canonical_xml(node).decode("utf-8")
    name = None
    based_on_id = None
    link_id = None
    ppr_bag = None
    rpr_bag = None
    for child in node:
        if not isinstance(child.tag, str):
            continue
        local = etree.QName(child.tag).localname if child.tag.startswith("{") else child.tag
        if local == "name" and name is None:
            name = _attr(child, "val")
        elif local == "basedOn" and based_on_id is None:
            based_on_id = _attr(child, "val")
        elif local == "link" and link_id is None:
            link_id = _attr(child, "val")
        elif local == "pPr" and ppr_bag is None:
            ppr_bag = _bag_from_element(child, f"{base_path}/w:pPr[1]")
        elif local == "rPr" and rpr_bag is None:
            rpr_bag = _bag_from_element(child, f"{base_path}/w:rPr[1]")
    return StyleEntry(
        style_id=_attr(node, "styleId") or "",
        style_type=_attr(node, "type") or "",
        is_default=_truthy(_attr(node, "default")),
        custom_style=_truthy(_attr(node, "customStyle")),
        based_on_id=based_on_id,
        link_id=link_id,
        name=name,
        ppr_bag=ppr_bag,
        rpr_bag=rpr_bag,
        structural_path=base_path,
        physical_hash=_physical_hash(canonical, {}),
    )


def _doc_defaults(root: etree._Element) -> DocDefaults | None:
    dd = root.find(_q("docDefaults"))
    if dd is None:
        return None
    rpr_bag = None
    ppr_bag = None
    rpr_default = dd.find(_q("rPrDefault"))
    if rpr_default is not None:
        rpr = rpr_default.find(_q("rPr"))
        if rpr is not None:
            rpr_bag = _bag_from_element(rpr, "/w:styles/w:docDefaults[1]/w:rPrDefault[1]/w:rPr[1]")
    ppr_default = dd.find(_q("pPrDefault"))
    if ppr_default is not None:
        ppr = ppr_default.find(_q("pPr"))
        if ppr is not None:
            ppr_bag = _bag_from_element(ppr, "/w:styles/w:docDefaults[1]/w:pPrDefault[1]/w:pPr[1]")
    return DocDefaults(rpr_bag=rpr_bag, ppr_bag=ppr_bag)


def build_style_catalog(package_bytes: bytes, physical_ir: dict) -> StyleCatalog:
    """Derive the StyleCatalog from OriginalPackage bytes + PhysicalIR inventory.

    Raises ValueError only on contract violation: disagreement between the
    provided package bytes and the PhysicalIR inventory for word/styles.xml.
    A missing part (on both sides) yields a valid empty catalog; an unreadable
    part yields a degraded catalog with `formatting_styles_part_unreadable`.
    """
    styles_bytes = _read_styles_bytes(package_bytes)
    inventory_hash = _inventory_sha256(physical_ir)

    if styles_bytes is None and inventory_hash is None:
        return StyleCatalog(
            part_name=STYLES_PART_NAME,
            part_sha256=None,
            part_status="missing",
            doc_defaults=None,
            styles=(),
            catalog_warnings=(),
        )
    if styles_bytes is None or inventory_hash is None:
        raise ValueError(
            "styles part present on exactly one side of package bytes / PhysicalIR inventory"
        )
    digest = hashlib.sha256(styles_bytes).hexdigest()
    if digest != inventory_hash:
        raise ValueError(
            f"sha256 mismatch for {STYLES_PART_NAME}: package {digest} != PhysicalIR {inventory_hash}"
        )

    try:
        root = etree.fromstring(styles_bytes, parser=_PARSER)
        if not isinstance(root.tag, str) or etree.QName(root.tag).localname != "styles" \
                or etree.QName(root.tag).namespace != W_NS:
            raise ValueError("unexpected styles root")
    except (etree.XMLSyntaxError, ValueError):
        return StyleCatalog(
            part_name=STYLES_PART_NAME,
            part_sha256=digest,
            part_status="unreadable",
            doc_defaults=None,
            styles=(),
            catalog_warnings=(
                AnalysisWarning(
                    code=W_STYLES_PART_UNREADABLE,
                    message="word/styles.xml could not be parsed; style levels degrade to unresolved.",
                    structural_path="/w:styles",
                ),
            ),
        )

    warnings: list[AnalysisWarning] = []
    styles: list[StyleEntry] = []
    style_index = 0
    for child in root:
        if not isinstance(child.tag, str):
            continue
        qn = etree.QName(child.tag)
        if qn.namespace == W_NS and qn.localname == "style":
            styles.append(_style_entry(child, style_index))
            style_index += 1

    seen: dict[str, int] = {}
    for entry in styles:
        if entry.style_id in seen:
            warnings.append(AnalysisWarning(
                code=W_DUPLICATE_STYLE_ID,
                message=f"Duplicate style id {entry.style_id!r} in styles.xml.",
                structural_path=entry.structural_path,
            ))
        else:
            seen[entry.style_id] = 1

    defaults_by_type: dict[str, list[StyleEntry]] = {}
    for entry in styles:
        if entry.is_default:
            defaults_by_type.setdefault(entry.style_type, []).append(entry)
    for style_type, entries in sorted(defaults_by_type.items()):
        if len(entries) > 1:
            warnings.append(AnalysisWarning(
                code=W_MULTIPLE_DEFAULT_STYLES,
                message=f"Multiple default styles of type {style_type!r}: "
                        f"{sorted(e.style_id for e in entries)}.",
                structural_path=entries[0].structural_path,
            ))

    return StyleCatalog(
        part_name=STYLES_PART_NAME,
        part_sha256=digest,
        part_status="ok",
        doc_defaults=_doc_defaults(root),
        styles=tuple(styles),
        catalog_warnings=tuple(warnings),
    )


def find_styles(catalog: StyleCatalog, style_id: str) -> tuple[StyleEntry, ...]:
    """All catalog entries with the given id (document order). >1 => duplicate."""
    return tuple(s for s in catalog.styles if s.style_id == style_id)


def default_styles(catalog: StyleCatalog, style_type: str) -> tuple[StyleEntry, ...]:
    return tuple(s for s in catalog.styles if s.is_default and s.style_type == style_type)
