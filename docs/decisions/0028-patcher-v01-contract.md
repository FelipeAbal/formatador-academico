# Decisão 0028 — Patcher/Applicator v0.1 contract

Status: **APPROVED FOR IMPLEMENTATION — adversarial audit integrated**

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

Patcher v0.1 is the first layer allowed to mutate DOCX bytes. It does not decide formatting, compliance, classification or safety. It executes one already-cleared SET_PROPERTY operation against the exact package snapshot supplied to it.

Principle:

**OperationPlan proposes; SafetyGate vetoes/releases; Patcher executes only the exact cleared mutation on the exact gated snapshot.**

Important: `GateClearedOperation` is not capability security. Python callers can fabricate internal-looking values. Therefore the patcher MUST independently revalidate snapshot identity, target resolution, target physical identity and operation shape before mutation. These checks are execution preconditions, not optional defense-in-depth.

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

`bytes` remains the package-snapshot type in v0.1. A separate `PackageSnapshot` model is not justified yet because Python bytes are immutable and PatchResult already carries package fingerprints.

## 4. Snapshot / TOCTOU precondition

Before opening XML or changing anything:

```text
sha256(package_snapshot)
==
cleared_operation.current_package_sha256
```

Mismatch => ordinary rejection `snapshot_hash_mismatch`, with no output bytes.

No path re-open after gating without revalidating the bytes. The bytes supplied to the patcher are the authoritative snapshot.

## 5. Immutability / atomicity

Input bytes are immutable.

Patcher works on an in-memory copy and returns new package bytes only after all preconditions and postconditions pass.

On any rejection/error:
- no partial output is considered valid;
- original bytes remain untouched;
- `output_package_bytes` is None;
- no partially mutated package is returned as applied.

## 6. Package scope and ZIP preservation

v0.1 mutates only:

```text
word/document.xml
```

All other ZIP part payload bytes MUST remain byte-identical after extraction.

The package entry set and entry order MUST remain identical.

For each ZIP entry, repackaging MUST preserve this metadata allowlist from the original entry:
- filename;
- date_time;
- compress_type;
- external_attr;
- internal_attr;
- create_system;
- per-entry comment;
- directory-entry identity.

The archive-level ZIP comment MUST also be preserved.

Do NOT blindly reuse all original ZipInfo fields. In particular do not copy stale CRC, compress_size, header_offset, ZIP64 extra fields or data-descriptor flag bits into the modified entry. Build a fresh ZipInfo using only the allowed preserved metadata required for correctness.

Compression level MUST be explicitly fixed by the patcher implementation so repeated output is deterministic within the supported runtime contract.

No new OOXML parts, relationships, content types or package entries may be added or removed.

## 7. XML parser and serializer safety

Use OOXML/lxml directly with secure parser settings equivalent to the frozen parser:
- resolve_entities=False;
- no_network=True;
- recover=False;
- DTD/DOCTYPE rejected;
- no external entity resolution.

python-docx is not authoritative and MUST NOT be used to rewrite the package.

Never call `cleanup_namespaces()` on the document tree. Inclusive c14n and physical hashes depend on namespace context.

The patcher MUST preserve document-level XML prolog information and nodes outside the document element:
- comments before/after the root;
- processing instructions before/after the root;
- XML declaration semantics;
- `standalone` state when present.

Therefore serialization MUST be performed from an `ElementTree`/document-level representation, not by serializing only the root element. The implementation must preserve relevant `docinfo` semantics rather than silently dropping them.

## 8. Parser helper reuse — required upstream surface

Patcher MUST reuse the parser's exact semantics for:
- canonical XML;
- inherited xml:space/xml:lang/xml:base;
- physical_hash;
- structural_path generation;
- structural_path resolution.

Before patcher implementation, promote the minimal parser helpers to a public additive API without changing behavior. Required conceptual surface:

```text
canonical_xml(node)
physical_hash(canonical_xml, inherited_xml_attrs)
inherited_xml_attrs(node)
structural_path(node, root)
resolve_structural_path(root, path) -> Element
```

This is an additive public surface, not a parser semantic change. Parser version need not bump if behavior remains byte-for-byte/semantic-equivalent to v0.4.0.

## 9. structural_path resolution

Target must be a run in `word/document.xml`.

Resolve the raw XML node using the frozen parser structural_path semantics:
- path rooted at the document story root;
- QName-sensitive;
- same-name sibling 1-based indices;
- no text matching;
- no heuristic matching;
- no prefix-string parent inference.

Example:

```text
/w:document/w:body[1]/w:p[1]/w:r[1]
```

`structural_path` is NOT an XPath language. The patcher MUST NOT pass it to `Element.xpath()`, `find()` or equivalent path engines. Resolution must be a dedicated inverse walk of the parser's path-generation semantics, including non-`w` namespaces and non-element nodes where supported.

Resolution must produce exactly one `w:r`.

If snapshot hash matched but target resolution yields zero/multiple nodes or wrong type, that indicates internal contract/path drift and is a `PatcherIntegrityError`, not an ordinary document rejection.

## 10. Physical identity recheck — mandatory integrity precondition

After exact target resolution and before mutation:
- recompute target physical_hash using the SAME parser semantics as Parser v0.4.0: inclusive canonical XML + inherited xml:space/xml:lang/xml:base;
- require equality with `cleared_operation.operation.target.physical_hash`.

Mismatch after a successful snapshot fingerprint match is impossible under a coherent implementation and therefore is a `PatcherIntegrityError`.

This is a mandatory execution-integrity precondition. The patcher does not trust token typing as proof that SafetyGate actually ran.

## 11. Allowed physical shape

For the targeted run, v0.1 accepts only canonical safe shapes.

All counting/location below is STRICTLY among DIRECT CHILDREN. Never use descendant-axis searches for `w:rPr`, `w:b` or `w:sz`.

Reject before mutation if:
- more than one direct `w:rPr` exists;
- one direct `w:rPr` exists but it is not the first child of `w:r`;
- targeted direct property appears more than once, even if duplicates are semantically identical;
- direct `w:rPr` contains `mc:AlternateContent`;
- existing direct `w:rPr` children are not in canonical schema order;
- target lies outside `word/document.xml`;
- the operation kind/property is outside the v0.1 executable slice;
- font-size value is not exactly representable under §15.

`w:rPrChange` is a protected historical container. Any nested `w:rPr`, `w:b` or `w:sz` inside it is not a direct target property, must not count as a duplicate, and must remain semantically/structurally untouched.

Reason: v0.1 is an executor, not a duplicate normalizer, revision normalizer or repair engine.

## 12. Creating/reusing w:rPr

If the run has no direct `w:rPr`, Patcher may create exactly one `w:rPr` as the first child of `w:r`, preserving all existing run children and text.

If one valid direct `w:rPr` exists as the first child, reuse it.

If >1 exists, or if the sole rPr is misplaced, reject.

An empty pre-existing `<w:rPr/>` is valid and must be reused rather than duplicated.

## 13. Canonical child order inside w:rPr — mandatory

`CT_RPr` / `EG_RPrBase` is sequence-ordered. Creating a property by naive append can yield schema-invalid OOXML that Word may repair.

The patcher MUST use a frozen canonical rank table, verified against the ECMA-376/XSD before implementation freeze. The v0.1 rank table must cover at least all legal direct children needed to position `w:b` and `w:sz` safely, including `w:rPrChange` as the trailing change-history element.

Reference order to verify in implementation tests:

```text
rStyle, rFonts, b, bCs, i, iCs, caps, smallCaps, strike, dstrike,
outline, shadow, emboss, imprint, noProof, snapToGrid, vanish, webHidden,
color, spacing, w, kern, position, sz, szCs, highlight, u, effect,
bdr, shd, fitText, vertAlign, rtl, cs, em, lang, eastAsianLayout,
specVanish, oMath,
then rPrChange
```

Insertion rule:
1. do not move any pre-existing sibling;
2. insert the new property immediately before the first existing direct child whose canonical rank is greater;
3. if none exists, insert before `w:rPrChange`;
4. otherwise append;
5. if existing direct rPr children are themselves out of canonical order, reject rather than repair.

Allowed-delta validation and postcondition Analysis do NOT substitute for this schema-order check.

## 14. Bold semantics

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

When one direct w:b exists, mutate only that property into the canonical target representation. When absent, create exactly one direct w:b under w:rPr at its canonical schema position.

No other run property is changed.

## 15. Font-size semantics

Operation desired value must be `LengthValue(value, unit="pt")`.

Convert only inside Patcher:

```text
half_points = points * 2
```

Requirements:
- Decimal semantics; never float;
- unit exactly `pt`;
- value finite and strictly positive;
- `points * 2` must be an exact integer;
- no rounding;
- output lexical form is canonical base-10 integer with no leading zeroes;
- upper bound: 3276 half-points / 1638 pt for v0.1.

Examples:

```text
12pt -> w:sz w:val="24"
11.5pt -> w:sz w:val="23"
11.25pt -> reject
0pt -> reject
```

Canonical action:
- if one direct `w:sz` exists, change only its `w:val`;
- if absent, create one direct `w:sz` under w:rPr at its canonical schema position;
- if >1 direct w:sz exists, reject;
- never touch `w:szCs`;
- never touch fonts, language, styles, or other rPr properties.

`w:szCs` is a deliberate v0.1 blind spot. It remains byte/semantic-intact even if it diverges from the new `w:sz`. This is safer than mutating an unauthorized subaspect. It MUST be covered by tests and recorded as a production-blocking debt before real-user deployment.

## 16. No implicit normalization

Patcher does not:
- reorder unrelated properties for aesthetics;
- repair out-of-order rPr children;
- remove redundant properties;
- normalize unrelated lexical forms;
- merge duplicate properties;
- clean whitespace/comments;
- rewrite styles;
- update metadata;
- rewrite tracked formatting history.

Only edits structurally necessary to realize the one cleared operation are permitted.

## 17. PatchResult

Frozen target model:

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

Unexpected programming/parser/integrity failures remain fail-fast exceptions rather than being disguised as ordinary rejection.

## 18. Error model

### Ordinary rejected outcomes

Closed v0.1 rejection vocabulary:
- `snapshot_hash_mismatch`;
- `unsupported_operation`;
- `noncanonical_run_properties`;
- `duplicate_target_property`;
- `unrepresentable_value`.

These mean the supplied operation/snapshot shape is outside what v0.1 can execute safely.

### Fail-fast integrity/contract exceptions

Examples:
- snapshot hash matched but target cannot be resolved exactly;
- target type differs from what the cleared operation declares;
- recomputed physical_hash differs after successful snapshot match;
- parser helper/path semantics disagree;
- output allowed-delta validation fails;
- output semantic postcondition fails;
- package part set changes unexpectedly;
- untouched part payload changes;
- serializer loses document-level nodes/docinfo unexpectedly.

Use explicit `PatcherError` / `PatcherContractError` / `PatcherIntegrityError` style separation.

Postcondition failure is NOT an ordinary rejected document condition; it indicates executor/serializer divergence and must fail-fast.

## 19. Postcondition verification — mandatory

A patch is not `applied` merely because XML serialization succeeded.

Before returning applied:
1. construct complete output DOCX bytes;
2. re-open/re-read the produced ZIP bytes, not just the in-memory tree;
3. parse output with the real frozen Parser;
4. build current StyleCatalog from output;
5. derive Analysis for the same target;
6. verify targeted semantic property == operation.desired_value;
7. verify target/content conservation through the allowed-delta validator;
8. verify every untouched package part payload is byte-identical;
9. verify package entry set and order are unchanged;
10. verify preserved ZIP metadata allowlist;
11. verify mutation is confined to the authorized property/wrapper;
12. verify property is in canonical schema position.

Any failure in these invariants is fail-fast `PatcherIntegrityError`, and no applied output escapes.

## 20. Allowed-delta validator — mandatory

Validation runs on bytes re-read from the produced ZIP.

Minimal robust algorithm:
1. parse original and output `word/document.xml` as document-level trees;
2. locate the target run in each using parser `resolve_structural_path` semantics;
3. remove the direct target `w:b` or `w:sz` from both comparison trees if present;
4. after removal, if the target `w:rPr` has no element children and no attributes, remove that empty wrapper from the comparison tree;
5. compare inclusive canonical XML of the resulting document elements byte-for-byte;
6. separately compare document-level siblings outside the root (comments/PIs) and relevant `docinfo` semantics;
7. separately verify the actual output target property has the exact canonical representation and schema position required by §§13–15.

This is not a generic XML diff engine. It is a narrow proof that the only authorized semantic OOXML delta is the target property plus a necessary newly-created rPr wrapper.

The validator must never neutralize `w:rPrChange` content or descendant target-looking nodes.

## 21. Text/content conservation

The allowed-delta validator implies whole-document semantic conservation outside the authorized delta, but directed tests are mandatory for:
- `w:t`;
- tabs/breaks/symbols;
- field code fragments and `w:instrText`;
- deleted text;
- hyperlinks/run containers;
- comments;
- processing instructions;
- tracked formatting history (`w:rPrChange`);
- unrelated attributes.

No text-bearing fragment or non-target node may be changed.

## 22. Target identity after mutation

The target physical_hash and hashes of its ancestors will normally change because canonical XML changed. This is expected.

`structural_path` remains the postcondition locator because same-QName sibling indexing is stable for the allowed mutation. Creating `w:rPr` may change positional `original_index` values of run children; postcondition logic MUST NOT compare `original_index` as identity.

Use structural_path + actual parsed target semantics, never original_index.

## 23. Determinism

Given identical input package bytes + identical GateClearedOperation under the same supported runtime/compression contract, output bytes MUST be identical.

Requirements:
- no current clock;
- preserve original ZipInfo date_time;
- explicitly fix compression level;
- preserve package entry order;
- deterministic lxml serialization settings;
- no random/locale/network/LLM.

## 24. Patcher version

```text
PATCHER_VERSION = "0.1"
```

## 25. Single-operation semantics and stale second token

One call applies one GateClearedOperation only.

This is intentionally sufficient for the first proof, but it has an important consequence: mutating a run changes that run's physical_hash and the package hash. Therefore another cleared token from the SAME SafetyGate report — especially bold + font_size on the same run — becomes stale after the first patch.

v0.1 MUST NOT iterate `SafetyGateReport.cleared_operations` and apply them sequentially without re-running the pipeline/gate.

The valid initial orchestration is conceptually:

```text
loop per mutation:
    current DOCX
    -> Parser
    -> Analysis
    -> Classification
    -> Decision
    -> OperationPlan
    -> SafetyGate
    -> Patcher(one operation)
    -> new current DOCX
```

A future atomic multi-operation transaction engine may remove this inefficiency, but it is outside v0.1.

## 26. Required tests before implementation freeze

At minimum:
1. snapshot hash mismatch => reject, no output;
2. raw PlannedOperation/wrong input type => contract rejection;
3. fabricated/replaced token targeting another operation cannot bypass patcher rechecks;
4. target resolution/path drift after matching snapshot => integrity error;
5. physical hash mismatch after matching snapshot => integrity error;
6. duplicate direct w:rPr => reject;
7. sole direct w:rPr not first child => reject;
8. empty pre-existing w:rPr reused;
9. duplicate direct w:b => reject;
10. duplicate direct w:sz => reject;
11. nested w:b/w:sz inside w:rPrChange do not count as duplicates and remain unchanged;
12. direct mc:AlternateContent in target rPr => reject;
13. out-of-order pre-existing rPr child sequence => reject;
14. dense rPr insertion places new w:b at exact canonical schema position without moving siblings;
15. dense rPr insertion places new w:sz at exact canonical schema position without moving siblings;
16. bold true canonical mutation;
17. bold false overrides inherited true via `<w:b w:val="0"/>`;
18. bold false from direct true;
19. bold true from direct false;
20. create rPr for bold;
21. font 11pt -> 12pt (`22 -> 24`);
22. inherited font size -> create direct w:sz;
23. create rPr for font size;
24. half-point 11.5pt -> 23;
25. non-half-point 11.25pt => reject, no rounding;
26. zero/negative/out-of-range font size => reject;
27. never touch w:szCs;
28. non-w namespace sibling/path proves custom resolver, not XPath;
29. run inside hyperlink resolves exactly;
30. run inside table cell resolves exactly;
31. XML prolog comment + PI preserved;
32. standalone declaration semantics preserved;
33. text/tab/br/sym conservation;
34. field code/instrText conservation;
35. deleted text conservation;
36. tracked rPrChange conservation;
37. untouched ZIP part payload byte identity;
38. package part set unchanged;
39. ZIP entry order unchanged;
40. ZIP STORED entry remains STORED;
41. directory entry external_attr preserved;
42. archive comment and entry comments preserved;
43. allowed-delta validator catches accidental unrelated XML mutation;
44. postcondition runs against bytes re-read from output ZIP;
45. postcondition Analysis desired value reached;
46. deterministic repeated output bytes across time boundary;
47. applying first token makes second same-report token stale and rejected on next snapshot;
48. E2E DOCX -> Parser -> Analysis -> Classification -> Decision -> OperationPlan -> SafetyGate -> Patcher for bold;
49. same E2E for font size;
50. full frozen regression suite preserved.

## 27. Production-blocking debt before real-user deployment

The following may remain outside implementation v0.1 but MUST be resolved before running this patcher on real user documents in production:
- `w:szCs` semantic coordination for complex-script text, or an explicit upstream authorization model for paired sz/szCs changes;
- broader real-DOCX corpus tests, including Word-produced revision markup and mixed-script runs;
- multi-operation transactional execution or an accepted orchestration cost model.

## 28. Explicit future work

- multi-operation atomic transaction;
- applying all cleared_operations in one call;
- TransformLog;
- user-facing report;
- review/highlight document;
- semantic ZIP equivalence for different gated bytes;
- patching styles.xml;
- secondary stories;
- spacing/alignment;
- normalization/repair of malformed or duplicate OOXML.

## 29. Adversarial audit integrated

Audit verdict: **APROVAR COM AJUSTES**.

Blocking findings incorporated before implementation:
- B1: schema-order insertion inside w:rPr;
- B2: direct-child-only property counting and protection of w:rPrChange;
- B3: ElementTree/document-level serialization preserving prolog/docinfo;
- I1: path/hash/postcondition divergence moved to fail-fast integrity errors;
- I2: patcher explicitly does not trust token typing as proof of prior gating;
- I3: parser helper reuse/promoted public surface required;
- I4: structural_path explicitly forbidden as XPath input;
- I5: w:szCs kept untouched but recorded as production-blocking debt;
- I6: stale second-token consequence explicitly documented and sequential same-report execution prohibited.

Contract is approved for implementation. Final implementation freeze will be a separate decision after code, tests and adversarial review.