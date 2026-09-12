"""RawPropertyBag — single analytical parser for property containers (v0.1b M1).

This is the ONLY place in the Formatting Resolution View that interprets XML
from `properties_raw` records of the PhysicalIR and from pPr/rPr elements of
styles.xml/docDefaults. Hardened local parsing: no entities, no network, no
recovery. Duplicate detection happens here (kept in document order); conflict
resolution policy lives in the resolver.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from ..docx_parser import _canonical_xml, _physical_hash, _prefixed_name, _qname_parts
from .formatting_model import RawProperty, RawPropertyBag

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)


def _parse_xml_fragment(canonical_xml: str) -> etree._Element:
    return etree.fromstring(canonical_xml.encode("utf-8"), parser=_PARSER)


def _bag_from_element(node: etree._Element, base_path: str) -> RawPropertyBag:
    canonical = _canonical_xml(node).decode("utf-8")
    entries: list[RawProperty] = []
    for child in node:
        if not isinstance(child.tag, str):
            continue
        name = _prefixed_name(child.tag)
        peers = [
            c for c in node
            if isinstance(c.tag, str) and _qname_parts(c.tag) == _qname_parts(child.tag)
        ]
        path = f"{base_path}/{name}[{peers.index(child) + 1}]"
        entries.append(
            RawProperty(
                property_name=name,
                raw_attrs=tuple((_prefixed_name(k), v) for k, v in child.attrib.items()),
                canonical_xml=_canonical_xml(child).decode("utf-8"),
                structural_path=path,
            )
        )
    return RawPropertyBag(
        source_path=base_path,
        source_hash=_physical_hash(canonical, {}),
        entries=tuple(entries),
    )


def bag_from_properties_raw(properties_raw: dict[str, Any] | None) -> RawPropertyBag | None:
    """Build a bag from a PhysicalIR `properties_raw` record (canonical XML)."""
    if properties_raw is None:
        return None
    canonical_xml = properties_raw.get("canonical_xml")
    structural_path = properties_raw.get("structural_path")
    if not canonical_xml or not structural_path:
        return None
    node = _parse_xml_fragment(canonical_xml)
    bag = _bag_from_element(node, structural_path)
    # Prefer the parser's own physical identity for the container.
    return RawPropertyBag(
        source_path=bag.source_path,
        source_hash=properties_raw.get("physical_hash") or bag.source_hash,
        entries=bag.entries,
    )


def bag_from_element(node: etree._Element, base_path: str) -> RawPropertyBag:
    """Build a bag from a live lxml element (used by the StyleCatalog builder)."""
    return _bag_from_element(node, base_path)
