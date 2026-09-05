"""Style identity map v0.1 — Classification Layer.

Closed, versioned, conservative map from verifiable document style identity
to target class (decision 0022). It operates on `style_id` / `basedOn`
identity resolved through the frozen StyleCatalog — never on style *names*,
never on formatting appearance, and never on normative rules.

Slice-1 built-in identities (audited against the OOXML/Word default id
convention used by the repository's synthetic DOCX fixtures; no real DOCX
corpus with ground truth exists yet, so the map stays minimal):

    Normal            -> body
    Heading1..Heading9 -> heading, level 1..9

`BodyText` was deliberately NOT admitted: its stability/identity could not be
verified against available evidence (briefing item 28). Expansion is additive
and requires a new versioned entry set.

A built-in identity is only verifiable when the catalog entry exists, is a
paragraph style, and is NOT marked `customStyle`. Custom styles may inherit a
class only through a basedOn chain that deterministically resolves to a
recognized built-in identity. Chains that cross a style-type boundary
(basedOn is normatively same-type in OOXML), cycles, dangling references and
chains ending in unrecognized identities never classify.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..analysis.formatting_model import StyleCatalog, StyleEntry
from ..analysis.style_catalog import find_styles
from .model import TargetClass

CLASSIFICATION_STYLE_IDENTITY_VERSION = "0.1"

_MAX_CHAIN_DEPTH = 32

_HEADING_IDS = {f"Heading{level}": level for level in range(1, 10)}
_BODY_IDS = {"Normal"}


class IdentityOutcome(str, Enum):
    IDENTIFIED = "identified"
    UNRECOGNIZED = "unrecognized"
    BROKEN_CHAIN = "broken_chain"


class IdentityVia(str, Enum):
    DIRECT_BUILTIN = "direct_builtin"
    BASED_ON_CHAIN = "based_on_chain"


@dataclass(frozen=True)
class StyleIdentityResolution:
    requested_style_id: str
    outcome: IdentityOutcome
    target_class: TargetClass | None
    level: int | None
    via: IdentityVia | None
    chain: tuple[str, ...]

    def __post_init__(self) -> None:
        identified = self.outcome is IdentityOutcome.IDENTIFIED
        if identified != (self.target_class is not None):
            raise ValueError("identified outcome iff target_class is not None")
        if identified and self.via is None:
            raise ValueError("identified outcome requires via")
        if not identified and self.via is not None:
            raise ValueError("non-identified outcome cannot carry via")


def _builtin_identity(entry: StyleEntry) -> tuple[TargetClass, int | None] | None:
    """Recognized built-in identity, or None.

    Requires exact style_id match on the closed built-in set, paragraph type
    and the absence of the customStyle flag. The display name is irrelevant.
    """
    if entry.style_type != "paragraph" or entry.custom_style:
        return None
    style_id = entry.style_id
    if style_id in _BODY_IDS:
        return (TargetClass.BODY, None)
    if style_id in _HEADING_IDS:
        return (TargetClass.HEADING, _HEADING_IDS[style_id])
    return None


def resolve_style_identity(catalog: StyleCatalog, style_id: str) -> StyleIdentityResolution:
    """Resolve a paragraph style reference to a verifiable class identity.

    Deterministic; never raises for bad document content. The first catalog
    entry with the id is the normative referent (decision 0016); duplicates
    were already warned about by the StyleCatalog.
    """
    chain: list[str] = [style_id]
    visited = {style_id}
    current_id: str | None = style_id
    depth = 0
    while current_id is not None and depth <= _MAX_CHAIN_DEPTH:
        depth += 1
        entries = find_styles(catalog, current_id)
        if not entries:
            return StyleIdentityResolution(
                requested_style_id=style_id,
                outcome=IdentityOutcome.BROKEN_CHAIN,
                target_class=None,
                level=None,
                via=None,
                chain=tuple(chain),
            )
        entry = entries[0]
        builtin = _builtin_identity(entry)
        if builtin is None and entry.style_type != "paragraph":
            # Wrong-type hop (audit item 13): OOXML basedOn is normatively
            # same-type. A paragraph style chain that reaches a non-paragraph
            # entry has crossed a type boundary, so any identity beyond it is
            # not verifiable; the chain is broken and never classifies.
            return StyleIdentityResolution(
                requested_style_id=style_id,
                outcome=IdentityOutcome.BROKEN_CHAIN,
                target_class=None,
                level=None,
                via=None,
                chain=tuple(chain),
            )
        if builtin is not None:
            target_class, level = builtin
            return StyleIdentityResolution(
                requested_style_id=style_id,
                outcome=IdentityOutcome.IDENTIFIED,
                target_class=target_class,
                level=level,
                via=(
                    IdentityVia.DIRECT_BUILTIN
                    if len(chain) == 1
                    else IdentityVia.BASED_ON_CHAIN
                ),
                chain=tuple(chain),
            )
        next_id = entry.based_on_id
        if next_id is None or next_id in visited:
            # Chain ended without a recognized identity, or cycles back.
            outcome = (
                IdentityOutcome.BROKEN_CHAIN
                if next_id is not None and next_id in visited
                else IdentityOutcome.UNRECOGNIZED
            )
            if next_id is not None and next_id in visited:
                chain.append(next_id)
            return StyleIdentityResolution(
                requested_style_id=style_id,
                outcome=outcome,
                target_class=None,
                level=None,
                via=None,
                chain=tuple(chain),
            )
        visited.add(next_id)
        chain.append(next_id)
        current_id = next_id
    return StyleIdentityResolution(
        requested_style_id=style_id,
        outcome=IdentityOutcome.BROKEN_CHAIN,
        target_class=None,
        level=None,
        via=None,
        chain=tuple(chain),
    )
