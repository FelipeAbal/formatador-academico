"""SafetyGate v0.1 — PhysicalIR target resolution helpers.

Resolution uses (planned story part + structural_path + target_type), never
a bare path over the whole document. Ancestry is obtained by walking the
actual PhysicalIR tree (parent chain), never by string-prefix inference on
`structural_path`.

Pure functions over the in-memory PhysicalIR mapping: no IO, no lxml, no
zipfile, no clock/randomness.
"""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from .model import SafetyGateContractError

# Factual PhysicalIR record types corresponding to each Decision/plan
# target_type, as produced by the frozen parser (decisions 0003-0012).
TARGET_RECORD_TYPES = {
    "paragraph": frozenset({"paragraph"}),
    "run": frozenset({"run_raw"}),
}


def walk_records(node: Any, ancestors: tuple[Mapping[str, Any], ...] = ()) -> Iterator[
    tuple[Mapping[str, Any], tuple[Mapping[str, Any], ...]]
]:
    """Yield (record, ancestor_chain) for every PhysicalIR record in the tree.

    The chain is ordered outermost-first; the last element is the direct
    parent record. Recursion follows any nested mapping carrying a
    `structural_path`, so paragraphs, runs, run_containers and table
    structures are all covered generically.
    """

    if isinstance(node, Mapping):
        if "structural_path" in node and "source_type" in node:
            yield node, ancestors
            ancestors = ancestors + (node,)
        for key in sorted(node):
            yield from walk_records(node[key], ancestors)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from walk_records(item, ancestors)


def find_story(physical_ir: Mapping[str, Any], part: str) -> Mapping[str, Any]:
    """Locate the unique story of the planned part in the current PhysicalIR."""

    stories = physical_ir.get("stories")
    if not isinstance(stories, (list, tuple)):
        raise SafetyGateContractError("current PhysicalIR lacks a stories sequence")
    matches = [
        story
        for story in stories
        if isinstance(story, Mapping) and story.get("part") == part
    ]
    if len(matches) != 1:
        raise SafetyGateContractError(
            f"current PhysicalIR must contain exactly one story for part {part!r}"
        )
    story = matches[0]
    if story.get("status") != "ok":
        raise SafetyGateContractError(
            f"current PhysicalIR story {part!r} is not in status 'ok'"
        )
    return story


def resolve_target(
    story: Mapping[str, Any], structural_path: str
) -> list[tuple[Mapping[str, Any], tuple[Mapping[str, Any], ...]]]:
    """All records of the story whose structural_path matches, with ancestry."""

    blocks = story.get("blocks")
    if not isinstance(blocks, (list, tuple)):
        raise SafetyGateContractError("current story lacks a blocks sequence")
    return [
        (record, ancestors)
        for record, ancestors in walk_records(blocks)
        if record.get("structural_path") == structural_path
    ]


def index_story_targets(
    story: Mapping[str, Any],
) -> dict[str, list[tuple[Mapping[str, Any], tuple[Mapping[str, Any], ...]]]]:
    """Index story records by path for one pure Gate evaluation.

    The index is only an evaluation-local acceleration. It preserves the
    ordered list and duplicate paths returned by ``resolve_target``.
    """

    blocks = story.get("blocks")
    if not isinstance(blocks, (list, tuple)):
        raise SafetyGateContractError("current story lacks a blocks sequence")
    indexed: dict[str, list[tuple[Mapping[str, Any], tuple[Mapping[str, Any], ...]]]] = {}
    for record, ancestors in walk_records(blocks):
        path = record.get("structural_path")
        if isinstance(path, str):
            indexed.setdefault(path, []).append((record, ancestors))
    return indexed


def paragraph_ancestor(
    ancestors: tuple[Mapping[str, Any], ...]
) -> Mapping[str, Any] | None:
    """Nearest real paragraph ancestor in the same story, via tree ancestry.

    Never inferred from a `structural_path` string prefix; covers
    paragraph -> run_container -> run nesting because the chain is built
    while walking the actual tree.
    """

    for record in reversed(ancestors):
        if record.get("source_type") == "paragraph":
            return record
    return None
