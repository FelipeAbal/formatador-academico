"""Parser v0.4.0 — public additive helper surface (decision 0028 §8).

This module exposes the exact frozen semantics of the parser that downstream
executors (Patcher v0.1) must reuse, WITHOUT changing parser behavior:

    canonical_xml(node) -> str
    inherited_xml_attrs(node) -> dict[str, str]
    physical_hash(canonical_xml, inherited_xml_attrs) -> str
    structural_path(node, root) -> str
    resolve_structural_path(root, path) -> node

The first four delegate to the frozen private implementations of
`docx_parser` (Parser v0.4.0); they are NOT reimplementations.

`resolve_structural_path` is the single new function: the literal inverse of
`_structural_path`. A structural path is NOT an XPath and is never passed to
`xpath()`/`find()`; resolution walks children step by step matching the real
QName (or comment/PI node kind) and the 1-based index among same-name
siblings, exactly as the parser generates it.
"""

from __future__ import annotations

import re

from lxml import etree

from .docx_parser import (
    W_NS,
    _canonical_xml as _parser_canonical_xml,
    _inherited_xml_attrs as _parser_inherited_xml_attrs,
    _node_kind_name as _parser_node_kind_name,
    _physical_hash as _parser_physical_hash,
    _structural_path as _parser_structural_path,
)

__all__ = [
    "canonical_xml",
    "inherited_xml_attrs",
    "physical_hash",
    "structural_path",
    "resolve_structural_path",
    "StructuralPathError",
]

_SEGMENT_RE = re.compile(r"^(?P<name>.+?)\[(?P<index>[1-9][0-9]*)\]$")


class StructuralPathError(ValueError):
    """Malformed structural path or unresolvable against the given root."""


def canonical_xml(node: etree._Element) -> str:
    """Inclusive canonical XML (c14n, with comments) of the node, as text.

    Identical semantics to Parser v0.4.0 `_canonical_xml`, decoded to str
    exactly as stored in the PhysicalIR `canonical_xml` field.
    """

    return _parser_canonical_xml(node).decode("utf-8")


def inherited_xml_attrs(node: etree._Element) -> dict[str, str]:
    """xml:space/xml:lang/xml:base inherited from ancestors (parser semantics)."""

    return _parser_inherited_xml_attrs(node)


def physical_hash(canonical_xml_text: str, inherited: dict[str, str]) -> str:
    """Physical fingerprint: sha256 over the frozen JSON payload."""

    return _parser_physical_hash(canonical_xml_text, inherited)


def structural_path(node: etree._Element, root: etree._Element) -> str:
    """Parser-frozen structural path of `node` relative to `root`."""

    return _parser_structural_path(node, root)


def _segment_matcher(name: str):
    """Compile one path segment name into a child predicate.

    Mirrors `_node_kind_name` exactly:
    - `w:local`      -> element in the WordprocessingML main namespace;
    - `{ns}local`    -> element in an arbitrary (possibly non-`w`) namespace;
    - `local`        -> element without namespace;
    - `comment()`    -> comment node;
    - `processing-instruction()` -> processing instruction node.
    """

    if name == "comment()":
        return lambda child: isinstance(child, etree._Comment)
    if name == "processing-instruction()":
        return lambda child: isinstance(child, etree._ProcessingInstruction)
    if name.startswith("w:"):
        tag = f"{{{W_NS}}}{name[2:]}"
        return lambda child: isinstance(child.tag, str) and child.tag == tag
    if name.startswith("{"):
        return lambda child: isinstance(child.tag, str) and child.tag == name
    return lambda child: isinstance(child.tag, str) and child.tag == name


def resolve_structural_path(root: etree._Element, path: str) -> etree._Element:
    """Resolve a parser structural path against `root` by explicit tree walk.

    This is the literal inverse of `structural_path`. It is NOT an XPath
    engine: each step selects the N-th (1-based) child of the current node
    whose real QName/node kind equals the segment name — the same semantics
    the parser used to generate the path. Non-`w` namespaces and non-element
    nodes (comment()/processing-instruction()) are supported.

    Raises StructuralPathError if the path is malformed, the root segment
    does not match, or any step cannot be resolved.
    """

    if not isinstance(path, str) or not path.startswith("/"):
        raise StructuralPathError(f"malformed structural path: {path!r}")
    segments = [s for s in path.split("/") if s != ""]
    if not segments:
        raise StructuralPathError(f"malformed structural path: {path!r}")

    root_name = _parser_node_kind_name(root)
    if segments[0] != root_name:
        raise StructuralPathError(
            f"path root segment {segments[0]!r} does not match root {root_name!r}"
        )

    current = root
    for segment in segments[1:]:
        match = _SEGMENT_RE.match(segment)
        if match is None:
            raise StructuralPathError(f"malformed path segment: {segment!r}")
        name, index = match.group("name"), int(match.group("index"))
        predicate = _segment_matcher(name)
        peers = [child for child in current if predicate(child)]
        if index > len(peers):
            raise StructuralPathError(
                f"unresolvable path segment {segment!r}: only {len(peers)} matching siblings"
            )
        current = peers[index - 1]
    return current
