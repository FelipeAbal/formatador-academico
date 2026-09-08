# Decisão 0028 — Patcher/Applicator v0.1 contract

Status: **PROPOSED — pending adversarial audit before freeze/implementation**

Date: 2026-09-08

Base architecture:

```text
OperationPlan
-> SafetyGate
-> GateClearedOperation
-> Patcher/Applicator
-> patched DOCX snapshot
```

## 1. Purpose

Patcher v0.1 is the first layer allowed to mutate DOCX bytes. It does not decide formatting, compliance, classification or safety. It executes one already-cleared SET_PROPERTY operation against the exact package snapshot that SafetyGate observed.

Principle:

**OperationPlan proposes; SafetyGate vetoes/releases; Patcher executes only the exact cleared mutation on the exact gated snapshot.**

## 2. First vertical slice

Executable in v0.1:

```text
P1 / run / bold
P2 / run / font_size
```

Outside v0.1:
- spacing.line;
- alignment;
- italic;
- P5-P27;
- structural MOVE/INSERT/MERGE;
- secondary stories;
- multiple-operation transaction;
- TransformLog;
- clean/review output orchestration;
- UI/API.

One patch call applies exactly one GateClearedOperation.

## 3. Public boundary

Conceptual API:

```text
apply_cleared_operation(
    package_snapshot: bytes,
    cleared_operation: GateClearedOperation,
) -> PatchResult
```

The patcher MUST NOT accept raw PlannedOperation as an executable input.

## 4. Snapshot / TOCTOU precondition

Before opening XML or changing anything:

```text
sha256(package_snapshot)
==
cleared_operation.current_package_sha256
```

Mismatch => reject/fail without mutation.

No path re-open after gating without revalidating the bytes. The bytes supplied to the patcher are the authoritative snapshot.

## 5. Immutability / atomicity

Input bytes are immutable.

Patcher works on an in-memory copy and returns new package bytes only after all preconditions and postconditions pass.

On any rejection/error:
- no partial output is considered valid;
- original bytes remain untouched;
- no partially mutated package is returned as applied.

## 6. Package scope

v0.1 mutates only:

```text
word/document.xml
```

All other ZIP part payload bytes MUST remain byte-identical after extraction.

ZIP container-level metadata/compressed byte representation may change as a consequence of repackaging, but payload bytes of every untouched part must be identical.

No new OOXML parts, relationships, content types or package entries may be added or removed.

## 7. XML parser safety

Use OOXML/lxml directly, with secure parser settings equivalent to the frozen parser:
- resolve_entities=False;
- no_network=True;
- recover=False;
- DTD/DOCTYPE rejected;
- no external entity resolution.

python-docx is not authoritative and MUST NOT be used to rewrite the package.

## 8. Target location

Target must be a run in `word/document.xml`.

Resolve the raw XML node using the frozen parser structural_path semantics:
- path rooted at document story root;
- QName-sensitive;
- same-name sibling 1-based indices;
- no text matching;
- no heuristic matching;
- no prefix-string parent inference.

Example shape:

```text
/w:document/w:body[1]/w:p[1]/w:r[1]
```

Resolution must produce exactly one `w:r`.

0 or >1 matches => reject.

## 9. Physical identity recheck

Even though SafetyGate already cleared the operation, Patcher performs defense-in-depth before mutation:
- resolve target node from structural_path;
- recompute the target physical_hash using the SAME semantics as Parser v0.4.0: canonical XML + inherited xml:space/xml:lang/xml:base;
- require equality with `cleared_operation.operation.target.physical_hash`.

Mismatch => reject before mutation.

The implementation should reuse/expose canonical parser helpers rather than fork subtly different hash/path semantics.

## 10. Allowed physical shape

For the targeted run, v0.1 accepts only canonical safe shapes.

Reject before mutation if:
- more than one direct `w:rPr` exists;
- targeted direct property appears more than once, even if duplicates are semantically identical;
- target is not a real `w:r`;
- target lies outside `word/document.xml`;
- required structure cannot be resolved exactly.

Reason: v0.1 is an executor, not a duplicate normalizer or repair engine.

## 11. Creating w:rPr

If the run has no `w:rPr`, Patcher may create exactly one `w:rPr` as the first child of `w:r`, preserving all existing run children and text.

If one `w:rPr` exists, reuse it.

If >1 exist, reject.

## 12. Bold semantics

Frozen Analysis semantics:
- `<w:b/>` => direct true;
- `<w:b w:val="1|true|on"/>` => direct true;
- `<w:b w:val="0|false|off"/>` => direct false;
- absence of direct `w:b` is NOT equivalent to false; cascade may inherit/toggle bold.

Therefore Patcher v0.1 canonical output is:

```text
desired bold = true
-> exactly one direct <w:b/>
```

```text
desired bold = false
-> exactly one direct <w:b w:val="0"/>
```

For false, do NOT remove w:b as an optimization: removal can expose inherited bold.

When one direct w:b exists, mutate only that property into the canonical target representation. When absent, create exactly one direct w:b under w:rPr.

No other run property is changed.

## 13. Font-size semantics

Operation desired value must be `LengthValue(value, unit="pt")`.

Convert only inside Patcher:

```text
half_points = points * 2
```

Requirements:
- value finite and positive;
- unit exactly `pt`;
- `points * 2` must be an exact non-negative integer representable as OOXML `w:sz` lexical integer;
- no rounding.

Example:

```text
12pt -> w:sz w:val="24"
```

Canonical action:
- if one direct `w:sz` exists, change only its `w:val`;
- if absent, create one direct `w:sz` under w:rPr;
- if >1 direct w:sz exists, reject;
- never touch `w:szCs`;
- never touch fonts, language, styles, or other rPr properties.

## 14. No implicit normalization

Patcher does not:
- reorder unrelated properties for aesthetics;
- remove redundant properties;
- normalize unrelated lexical forms;
- merge duplicate properties;
- clean whitespace/comments;
- rewrite styles;
- update metadata.

Only edits structurally necessary to realize the one cleared operation are permitted.

## 15. PatchResult

Proposed frozen model:

```text
PatchStatus = applied | rejected

PatchResult:
    patcher_version
    status
    operation_ref
    operation_plan_ref
    input_package_sha256
    output_package_sha256 | None
    output_package_bytes | None
    reason | None
    changed_part | None
```

For `applied`:
- output bytes required;
- output sha required;
- changed_part == `word/document.xml`;
- reason == None.

For `rejected`:
- output bytes == None;
- output sha == None;
- reason required.

Unexpected programming/parser exceptions remain fail-fast exceptions rather than being disguised as ordinary rejection.

## 16. Rejection reasons v0.1

Keep a small closed vocabulary, for example:
- `snapshot_hash_mismatch`;
- `unsupported_operation`;
- `target_not_found`;
- `target_not_unique`;
- `target_type_mismatch`;
- `physical_hash_mismatch`;
- `noncanonical_run_properties`;
- `duplicate_target_property`;
- `unrepresentable_value`;
- `postcondition_failed`.

Exact names may be refined during adversarial audit, but semantics must remain narrow.

## 17. Postcondition verification — mandatory

A patch is not `applied` merely because XML serialization succeeded.

Before returning applied:
1. construct output DOCX bytes;
2. parse output with the frozen real Parser;
3. build current StyleCatalog from output;
4. derive Analysis for the same target;
5. verify targeted semantic property == operation.desired_value;
6. verify target text/content was not changed;
7. verify all untouched package part payloads are byte-identical;
8. verify no package parts were added/removed;
9. verify mutation is confined to the authorized target/property under the allowed-delta validator below.

Failure => `postcondition_failed` and no applied output.

## 18. Allowed-delta validator

Because lxml serialization may change lexical XML representation without semantic mutation, v0.1 should validate XML structurally/canonically rather than require byte-identical `word/document.xml`.

Required principle:

**If the targeted property is normalized away from both pre- and post-patch target trees, the remaining canonical document tree must be equivalent.**

In other words, prove that the only semantic OOXML delta is:
- creation/change of target `w:rPr` if required;
- creation/change of exactly the targeted `w:b` or `w:sz`;
- no other element/attribute/text/comment delta.

If creating a previously absent `w:rPr`, the validator accounts only for that necessary wrapper plus the targeted property.

This validator is mandatory before `applied`.

## 19. Text/content conservation

All text-bearing and non-target run children must be unchanged.

No changes to:
- `w:t` text;
- tabs/breaks/symbols;
- field code fragments;
- deleted text;
- hyperlinks/container content;
- comments/processing instructions;
- unrelated attributes.

## 20. Target after mutation

The target physical_hash will normally change because its canonical XML changed. This is expected.

PatchResult records package before/after hashes. Future TransformLog may record target before/after hashes; not required in this slice unless implementation naturally provides them.

## 21. Determinism

Given identical input package bytes + identical GateClearedOperation, semantic patched output must be identical.

ZIP metadata/timestamps must NOT use current clock. Repackaging must use deterministic metadata or preserve original ZipInfo metadata so repeated patch calls do not create time-dependent outputs.

This also avoids repeating the known synthetic `build_docx` timestamp flake in production patching.

## 22. Patcher version

Proposed:

```text
PATCHER_VERSION = "0.1"
```

No LLM, network, clock, random, locale or external services.

## 23. Required tests before freeze

At minimum:
1. snapshot hash mismatch => reject, no output;
2. wrong token/raw PlannedOperation => API/type rejection;
3. target missing;
4. target nonunique artificial case;
5. wrong target type;
6. physical hash mismatch before XML mutation;
7. duplicate w:rPr => reject;
8. duplicate direct w:b => reject;
9. duplicate direct w:sz => reject;
10. bold true direct true canonical mutation;
11. bold false overrides inherited true via `<w:b w:val="0"/>`;
12. bold false from direct true;
13. bold true from direct false;
14. create rPr for bold;
15. font 11pt -> 12pt (`22 -> 24`);
16. inherited font size -> create direct w:sz;
17. create rPr for font size;
18. half-point representable e.g. 11.5pt -> 23;
19. non-half-point value => reject, no rounding;
20. never touch w:szCs;
21. text byte/semantic conservation;
22. untouched ZIP part payload byte identity;
23. package part set unchanged;
24. allowed-delta validator catches accidental unrelated XML change;
25. postcondition Analysis desired value reached;
26. deterministic repeated output bytes;
27. no current timestamp in output behavior;
28. end-to-end DOCX -> Parser -> Analysis -> Classification -> Decision -> OperationPlan -> SafetyGate -> Patcher for bold;
29. same end-to-end for font size;
30. full frozen regression suite preserved.

## 24. Explicit non-goals / future work

- multi-operation atomic transaction;
- applying all cleared_operations in one call;
- TransformLog;
- user-facing report;
- review/highlight document;
- semantic ZIP equivalence for different gated bytes;
- patching styles.xml;
- secondary stories;
- spacing/alignment;
- normalization of malformed/duplicate OOXML.

## 25. Audit questions before freeze

Adversarial audit must specifically attack:
1. whether structural_path can be safely and exactly resolved back into raw lxml without path-semantic drift;
2. whether physical_hash recomputation shares code with Parser rather than duplicating logic;
3. whether lxml serialization can create hidden unrelated semantic deltas and whether allowed-delta validation closes that risk;
4. whether ZIP repackaging preserves untouched part payload bytes and deterministic output;
5. whether bold false canonical direct override is correct under frozen toggle semantics;
6. whether duplicate properties/rPr must reject rather than normalize;
7. whether postcondition Analysis on the output is sufficient to prove desired semantics without reauthorizing anything;
8. whether any path exists to execute raw PlannedOperation or bypass GateClearedOperation;
9. whether PatchResult should return bytes directly or a separate immutable package snapshot type;
10. whether any failure mode could return partially mutated bytes as `applied`.
